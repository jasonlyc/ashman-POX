def ip_str(index):
    pod = int(index / 16)
    edge = int((index % 16) / 4)
    host = index % 4 + 2
    return "10.%i.%i.%i" % (pod, edge, host)

def GenAllToAllInput():
    data = open('inputs/all_to_all_data', 'w')
    for src in range(0, 128):
        for dst in range(0, 128):
            if src != dst:
                data.write("%s %s " % (ip_str(src), ip_str(dst)))
                if not (src == 127 and dst == 127):
                    data.write("\n")
    data.close()

def GenStrideInput():
    data = open('inputs/stride1_data', 'w')
    for index in range(0, 128):
        data.write("%s %s " % (ip_str(index), ip_str((index + 1) % 128)))
        if index != 127:
            data.write("\n")
    data.close()

    data = open('inputs/stride2_data', 'w')
    for index in range(0, 128):
        data.write("%s %s " % (ip_str(index), ip_str((index + 2) % 128)))
        if index != 127:
            data.write("\n")
    data.close()

    data = open('inputs/stride4_data', 'w')
    for index in range(0, 128):
        data.write("%s %s " % (ip_str(index), ip_str((index + 4) % 128)))
        if index != 127:
            data.write("\n")
    data.close()

    data = open('inputs/stride8_data', 'w')
    for index in range(0, 128):
        data.write("%s %s " % (ip_str(index), ip_str((index + 8) % 128)))
        if index != 127:
            data.write("\n")
    data.close()

def GenOtherInput():
    input_list = ['stag_prob_0_2_3_data', 'stag_prob_1_2_3_data', 'stag_prob_2_2_3_data', 'stag_prob_0_5_3_data', 'stag_prob_1_5_3_data', 'stag_prob_2_5_3_data', 'random0_data', 'random1_data', 'random2_data', 'random0_bij_data', 'random1_bij_data', 'random2_bij_data', 'random_2_flows_data', 'random_3_flows_data', 'random_4_flows_data', 'all_to_all_data']
    for element in input_list:
        data = open('inputs/%s' % element, 'w')
        source = open('inputs_bak/%s' % element, 'r')
        first_line = True
        for line in source:
            if (line[0] == '#'):
                continue
            flow = line.split(' ')
            src_ip = flow[0]
            dst_ip = flow[1]
            src_info = src_ip.split('.')
            dst_info = dst_ip.split('.')
            src_pod = int(src_info[1])
            dst_pod = int(dst_info[1])
            src_edge = int(src_info[2])
            dst_edge = int(dst_info[2])
            src_host = int(src_info[3])
            dst_host = int(dst_info[3])
            if not first_line:
                data.write("\n")
            else:
                first_line = False
            data.write("10.%i.%i.%i 10.%i.%i.%i \n" %(src_pod, src_edge, src_host, dst_pod, dst_edge, dst_host))
            data.write("10.%i.%i.%i 10.%i.%i.%i \n" %(src_pod, src_edge, src_host + 2, dst_pod, dst_edge, dst_host + 2))
            data.write("10.%i.%i.%i 10.%i.%i.%i \n" %(src_pod, src_edge + 2, src_host, dst_pod, dst_edge + 2, dst_host))
            data.write("10.%i.%i.%i 10.%i.%i.%i \n" %(src_pod, src_edge + 2, src_host + 2, dst_pod, dst_edge + 2, dst_host + 2))
            data.write("10.%i.%i.%i 10.%i.%i.%i \n" %(src_pod + 4, src_edge, src_host, dst_pod + 2, dst_edge, dst_host))
            data.write("10.%i.%i.%i 10.%i.%i.%i \n" %(src_pod + 4, src_edge, src_host + 2, dst_pod + 2, dst_edge, dst_host + 2))
            data.write("10.%i.%i.%i 10.%i.%i.%i \n" %(src_pod + 4, src_edge + 2, src_host, dst_pod + 2, dst_edge + 2, dst_host))
            data.write("10.%i.%i.%i 10.%i.%i.%i " %(src_pod + 4, src_edge + 2, src_host + 2, dst_pod + 2, dst_edge + 2, dst_host + 2))
        data.close()
        source.close()


if __name__ == '__main__':
    GenAllToAllInput()
    GenStrideInput()
    GenOtherInput()
