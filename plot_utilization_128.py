'''
@author: Milad Sharif(msharif@stanford.edu)
'''

from monitor.helper import *
from math import fsum
import numpy as np

BW=1

parser = argparse.ArgumentParser()
parser.add_argument('--input', '-f', dest='files', required=True, help='Input rates')
parser.add_argument('--out', '-o', dest='out', default=None, 
        help="Output png file for the plot.")

args= parser.parse_args()


''' Output of bwm-ng has the following format:
    unix_timestamp;iface_name;bytes_out;bytes_in;bytes_total;packets_out;packets_in;packets_total;errors_out;errors_in
    '''

traffics=['stag_prob_0_2_3_data', 'stag_prob_1_2_3_data', 'stag_prob_2_2_3_data',
        'stag_prob_0_5_3_data','stag_prob_1_5_3_data','stag_prob_2_5_3_data','stride1_data', 
        'stride2_data', 'stride4_data', 'stride8_data', 'random0_data', 'random1_data', 'random2_data', 
        'random0_bij_data', 'random1_bij_data','random2_bij_data', 'random_2_flows_data', 
        'random_3_flows_data', 'random_4_flows_data','all_to_all_data']

labels=['stag0(0.2,0.3)', 'stag1(0.2,0.3)', 'stag2(0.2,0.3)', 'stag0(0.5,0.3)',
        'stag1(0.5,0.3)', 'stag2(0.5,0.3)', 'stride1', 'stride2',
        'stride4','stride8','rand0', 'rand1', 'rand2','randbij0',
        'randbij1','randbij2','randx2','randx3','randx4','all_to_all']


def get_utilization(input_file, pat_iface):
    pat_iface = re.compile(pat_iface)
    
    data = read_list(input_file)

    utilization = {} 
    column_tx = 2
    column_rx = 3
        
    for row in data:
        try:
            ifname = row[1]
        except:
            break

        if ifname not in ['eth0', 'lo']:
            if not utilization.has_key(ifname):
                utilization[ifname] = []
            
            try:
                utilization[ifname].append(float(row[column_tx]) * 8 / (1 << 20) + float(row[column_rx]) * 8 / (1 << 20))
            except:
                break
    vals = []
    for k in utilization.keys():
        if pat_iface.match(k): 
            avg_rate = avg(utilization[k][20:-20])
            vals.append(avg_rate)
            
    return fsum(vals)

def plot_results(args):


    output_file = open("utilization.txt", 'w');
    num_plot = 2
    num_t = 20
    n_t = num_t/num_plot

    bb = {'nonblocking' : [],'hedera' :  [], 'ashman_bestfit' : [], 'ashman_probfit' : [], 'ecmp' : []}

    sw = '8h1h1'
    output_file.write('Nonblocking:\n');
    for t in traffics:
        print "Nonblocking:", t
        input_file = args.files + '/nonblocking/%s/rate.txt' % t    
        vals = get_utilization(input_file, sw) / (128 * BW)
        bb['nonblocking'].append(vals)
        output_file.write('%s: %.3f\n' %(t, vals))

    sw = '[0-7]h[0-7]h1-eth[1-4]|8h[1-4]h[1-4]'
    output_file.write('ECMP:\n');
    for t in traffics:
        print "ECMP:", t
        input_file = args.files + '/fattree-ecmp/%s/rate.txt' % t
        vals = get_utilization(input_file, sw) / (384 * BW)
        bb['ecmp'].append(vals)
        output_file.write('%s: %.3f\n' %(t, vals))
   
    output_file.write('Hedera_FirstFit\n')
    for t in traffics:
       print "Hedera_FirstFit:", t
       input_file = args.files + '/fattree-hedera/%s/rate.txt' % t
       vals = get_utilization(input_file, sw) / (384 * BW)
       bb['hedera'].append(vals)
       output_file.write('%s: %.3f\n' %(t, vals))

    output_file.write('Ashman_BestFit:\n')
    for t in traffics:
       print "Ashman_BestFit:", t
       input_file = args.files + '/fattree-ashman-bestfit/%s/rate.txt' % t
       vals = get_utilization(input_file, sw) / (384 * BW)
       bb['ashman_bestfit'].append(vals)
       output_file.write('%s: %.3f\n' %(t, vals))

    output_file.write('Ashman_ProbFit:\n')
    for t in traffics:
        print "Ashman_ProbFit:", t
        input_file = args.files + '/fattree-ashman-probfit/%s/rate.txt' % t
        vals = get_utilization(input_file, sw) / (384 * BW)
        bb['ashman_probfit'].append(vals)
        output_file.write('%s: %.3f\n' %(t, vals))

    output_file.close()


    ind = np.arange(n_t)
    width = 0.15
    fig = plt.figure(1)
    fig.set_size_inches(18.5,6.5)

    for i in range(num_plot):
        fig.set_size_inches(24,12)

        ax = fig.add_subplot(2,1,i+1)
        ax.yaxis.grid()

        plt.ylim(0.0, 1.0)
        plt.xlim(0,10)
        plt.ylabel('Normalized Average Bandwidth Utilization')
        plt.xticks(ind + 3.5*width, labels[i*n_t:(i+1)*n_t])
    
        # Nonblocking
        p1 = plt.bar(ind + 5.5*width, bb['nonblocking'][i*n_t:(i+1)*n_t], width=width,
                color='royalblue')

        # FatTree + Ashman_ProbFit
        p2 = plt.bar(ind + 4.5*width, bb['ashman_probfit'][i*n_t:(i+1)*n_t], width=width, color='yellow')

        # FatTree + Ashman_BestFit
        p3 = plt.bar(ind + 3.5*width, bb['ashman_bestfit'][i*n_t:(i+1)*n_t], width=width, color='black')

        # FatTree + Hedera
        p4 = plt.bar(ind + 2.5*width, bb['hedera'][i*n_t:(i+1)*n_t], width=width, color='green')

        # FatTree + ECMP
        p5 = plt.bar(ind + 1.5*width, bb['ecmp'][i*n_t:(i+1)*n_t], width=width, color='brown')

        plt.legend([p1[0], p2[0], p3[0], p4[0], p5[0]],['Non-blocking', 'Ashman ProbFit', 'Ashman BestFit', 'Hedera', 'ECMP'],loc='upper left')

        plt.savefig(args.out)


plot_results(args)
