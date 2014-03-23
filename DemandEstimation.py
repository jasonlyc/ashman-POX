'''the demand estimation algorithm from Hedera paper is implemented here'''
import random
import pdb

def demand_estimation(flows, hostsList):
    M ={} 
    for i in hostsList:
        M[i] = {}
        for j in hostsList:
            M[i][j] = {'demand': 0, 'demandInit': 0, 'converged' : False, 'FlowNmbr' : 0}
  
    for flow in flows:
        M[flow['src']][flow['dst']]['FlowNmbr'] += 1
     
    demandChange = True
    while demandChange:
       demandChange = False  
       for src in hostsList:
            Est_Src(M, flows, src)
       
       for dst in hostsList:
            Est_Dst(M, flows, dst)

       for i in hostsList:
           for j in hostsList:
               if M[i][j]['demandInit'] != M[i][j]['demand']:
                   demandChange = True
                   M[i][j]['demandInit'] = M[i][j]['demand']
       
    #print"********************estimated demands*********************\n", demandsPrinting(M,hostsList)
    print 'estimation completes'
    return (M, flows)

def Est_Src(M, flows, src):
    dF = 0
    nU = 0
    for flow in flows:
        if flow['src'] == src:
            if flow['converged']:
                dF += flow['demand']
            else:
                nU += 1
    if nU != 0:
        
        eS = (1.0 - dF) / nU
        for flow in flows:
            if flow['src'] == src and not flow['converged']:
                M[flow['src']][flow['dst']]['demand'] = eS
                #pdb.set_trace()  
                flow['demand'] = eS

            
def Est_Dst(M, flows, dst):
    dT = 0
    dS = 0
    nR = 0
    for flow in flows:
        if flow['dst'] == dst:
            flow['recLimited'] = True
            dT += flow['demand']
            nR += 1
    if dT <= 1.0:
        return
    eS = 1.0 / nR

    flagFlip=True
    while flagFlip:
        flagFlip = False
        nR = 0
        for flow in flows:
            if flow['dst'] == dst and flow['recLimited']:
                if flow['demand'] < eS:
                    dS += flow['demand']
                    flow['recLimited'] = False
                    flagFlip = True
                else:
                    nR += 1

        eS = (1.0-dS)/nR
            
    for flow in flows:
        if flow['dst'] == dst and flow['recLimited']:
            M[flow['src']][flow['dst']]['demand'] = eS
            M[flow['src']][flow['dst']]['converged'] = True
            flow['converged'] = True
            flow['demand'] = eS


def demandsPrinting(M,hostsList):
    print hostsList, '\n', '_'*80
    for row in hostsList:
        #pdb.set_trace() 
        print row,'|',
        for col in hostsList:
            temp = M[row][col]
            print '%.2f' % temp['demand'],
        print
def makeFlows(flows, src, dsts):
    demand = 0.2 / len(dsts)
    for dst in dsts:
        flows.append({'converged': False, 'demand': demand, 'src': src, 'dst': dst, 'recLimited': False})


if __name__ == '__main__':
    
    hostsList = range(15)
    flows = []

    for i in range(15):
        dst = random.randint(0,14)
        if dst > 6:
            makeFlows(flows, i, [dst, dst])
        else: 
            makeFlows(flows, i, [dst, dst+1])
 
    #pdb.set_trace()
    M, flows_estimated = demand_estimation(flows, hostsList)
    demandsPrinting(M,hostsList)
    #pdb.set_trace()
 
