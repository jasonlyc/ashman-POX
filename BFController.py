''' Hedera data center controller

@author: Behnam Montazeri (behnamm@stanford.edu)
'''

import logging

import sys

from struct import pack
from zlib import crc32

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import EventMixin
from pox.lib.util import dpidToStr

from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.udp import udp
from pox.lib.packet.tcp import tcp

from util import buildTopo, getRouting
from DemandEstimation import demand_estimation
from threading import Timer, Lock

log = core.getLogger()

# Number of bytes to send for packet_ins
MISS_SEND_LEN = 2000

class Switch(EventMixin):
    def __init__(self):
        self.connection = None
        self.dpid = None
        self.ports = None

    def connect(self, connection):
        if self.dpid is None:
            self.dpid = connection.dpid
        assert self.dpid == connection.dpid
        self.connection = connection

    def send_packet_data(self, outport, data = None):
        msg = of.ofp_packet_out(in_port=of.OFPP_NONE, data = data)
        msg.actions.append(of.ofp_action_output(port = outport))
        self.connection.send(msg)

    def send_packet_bufid(self, outport, buffer_id = -1):
        msg = of.ofp_packet_out(in_port=of.OFPP_NONE)
        msg.actions.append(of.ofp_action_output(port = outport))
        msg.buffer_id = buffer_id
        self.connection.send(msg)

    def install(self, port, match, buf = -1, deleteFlow=False, idle_timeout = 0 ):
        msg = of.ofp_flow_mod()
        msg.match = match
        msg.idle_timeout = idle_timeout
        msg.actions.append(of.ofp_action_output(port = port))
        if deleteFlow:
            msg.command = of.OFPFC_DELETE
        #msg.buffer_id = buf          
        msg.flags = of.OFPFF_SEND_FLOW_REM

        self.connection.send(msg)


class BFController(EventMixin):
    def __init__(self, t, r, bw, ratio):
        self.switches = {}  # [dpid]->switch
        self.macTable = {}  # [mac]->(dpid, port)
        self.t = t          # Topo object
        self.r = r          # Routng object
        self.all_switches_up = False
        core.openflow.addListeners(self)
        
        self.statCntr = 0 #sanity check for the flow stats     
        self.HostNameList = [] #a dictionary of the host
        self.hostsList = [] #list of host dpid
        self.flows = [] #list of the collected stats
        self.bw = bw
        self.ratio = ratio
        self.beReservation = {} #reservation for the elephant flows 
        self.statMonitorLock = Lock() #to lock the multi access threads 
        self.statMonitorLock.acquire()
        statMonitorTimer = Timer(10.0,self._collectFlowStats()) #timer to collect stats
        statMonitorTimer.start()
        self.matchDict = {} # dictioanary of the matches
    def _ecmp_hash(self, packet):
        ''' Return an ECMP-style 5-tuple hash for TCP/IP packets, otherwise 0.
        RFC2992 '''
        hash_input = [0] * 5
        if isinstance(packet.next, ipv4):
            ip = packet.next
            hash_input[0] = ip.srcip.toUnsigned()
            hash_input[1] = ip.dstip.toUnsigned()
            hash_input[2] = ip.protocol
            if isinstance(ip.next, tcp) or isinstance(ip.next, udp):
                l4 = ip.next
                hash_input[3] = l4.srcport
                hash_input[4] = l4.dstport
                return crc32(pack('LLHHH', *hash_input))
        return 0


    def _flood(self, event):
        ''' Broadcast to every output port '''
        packet = event.parsed
        dpid = event.dpid
        in_port = event.port
        t = self.t
        # Broadcast to every output port except the input on the input switch.
        for sw_name in t.layer_nodes(t.LAYER_EDGE):
            for host_name in t.lower_nodes(sw_name):
                sw_port, host_port = t.port(sw_name, host_name)
                sw = t.node_gen(name = sw_name).dpid

                # Send packet out each non-input host port
                if sw != dpid or (sw == dpid and in_port != sw_port):
                    self.switches[sw].send_packet_data(sw_port, event.data)


    def _install_reactive_path(self, event, out_dpid, final_out_port, packet):
        ''' Install entries on route between two switches. '''
        in_name = self.t.node_gen(dpid = event.dpid).name_str()
        out_name = self.t.node_gen(dpid = out_dpid).name_str()
        hash_ = self._ecmp_hash(packet)
        route = self.r.get_route(in_name, out_name, hash_)
        #print "Route:",route        
        #print '-'*80
        if route == None:
            print None, "route between", in_name, "and", out_name
            return

        match = of.ofp_match.from_packet(packet)

        for i, node in enumerate(route):
            node_dpid = self.t.node_gen(name = node).dpid
            if i < len(route) - 1:
                next_node = route[i + 1]
                out_port, next_in_port = self.t.port(node, next_node)
            else:
                out_port = final_out_port
            self.switches[node_dpid].install(out_port, match, idle_timeout = 10)

        if isinstance(packet.next, of.ipv4) and isinstance(packet.next.next, of.tcp):
            self.matchDict[(packet.next.srcip, packet.next.dstip, packet.next.next.srcport, packet.next.next.dstport)] = (route, match)
     
    def _handle_PacketIn(self, event):
        if not self.all_switches_up:
            #log.info("Saw PacketIn before all switches were up - ignoring." )
            return

        packet = event.parsed
        dpid = event.dpid
        in_port = event.port

        # Learn MAC address of the sender on every packet-in.
        self.macTable[packet.src] = (dpid, in_port)
        sw_name = self.t.node_gen(dpid = dpid).name_str()
        #print "Sw:", sw_name, packet.src, packet.dst,"port", in_port, packet.dst.isMulticast(),"macTable", packet.dst in self.macTable
        #print '-'*80
        
        # Insert flow, deliver packet directly to destination.

        if packet.dst in self.macTable:
            out_dpid, out_port = self.macTable[packet.dst]
            self._install_reactive_path(event, out_dpid, out_port, packet)

            self.switches[out_dpid].send_packet_data(out_port, event.data)

        else:
            self._flood(event)

    def _handle_ConnectionUp(self, event):
        sw = self.switches.get(event.dpid)
        sw_str = dpidToStr(event.dpid)
        sw_name = self.t.node_gen(dpid = event.dpid).name_str()

        if sw_name not in self.t.switches():
            log.warn("Ignoring unknown switch %s" % sw_str)
            return

        #log.info("A new switch came up: %s", sw_str)
        if sw is None:
            log.info("Added a new switch %s" % sw_name)
            sw = Switch()
            self.switches[event.dpid] = sw
            sw.connect(event.connection)

        sw.connection.send(of.ofp_set_config(miss_send_len=MISS_SEND_LEN))

        if len(self.switches)==len(self.t.switches()):
            log.info("All of the switches are up")
            self.all_switches_up = True
            if self.statMonitorLock.locked():
                self.statMonitorLock.release()    


    def _collectFlowStats(self):
        log.info("attempt to capture STATS") 
        ''' this function send the flow stat requests'''
        if not self.statMonitorLock.locked():
            # log.info("here it goes to monitor flow stats") 
            self.statMonitorLock.acquire()
            self.statCntr = 0
            self.flows = []
            self.HostNameList = []
            self.hostsList = []
            for sw_name in self.t.layer_nodes(self.t.LAYER_EDGE):
                sw_dpid = self.t.node_gen(name = sw_name).dpid
                #print 'sw_dpid',sw_dpid ,'sw_name',sw_name
                for port in range(1,self.t.k + 1):
                    if not self.t.isPortUp(port):
                        msg = of.ofp_stats_request()
                        msg.type = of.OFPST_FLOW
                        msg.body = of.ofp_flow_stats_request()
                        msg.body.out_port = port
                        self.switches[sw_dpid].connection.send(msg)
                        self.statCntr += 1
            self.statMonitorLock.release()
        statMonitorTimer = Timer(3.5, self._collectFlowStats)
        statMonitorTimer.start()


    def IP2name_dpid(self,IP):
        IP = str(IP)
        ten, p, e, h = (int(s) for s in IP.split('.'))
        node_name = self.t.node_gen(p,e,h).name_str()
        dpid_ = (p << 16) + (e << 8) + h
        return (node_name, dpid_)

    def _handle_FlowStatsReceived(self, event): 
        '''handle function for collected stats '''
        # log.info( "flow stat collected, process begins") 
        #print 'event.stats', event.stats
        self.statCntr -= 1
        for stat in event.stats:
            flowLivingTime = stat.duration_sec * 1e9 + stat.duration_nsec
            if flowLivingTime <= 1:
                flowLivingTime = 1
            flowDemand = 8 * float(stat.byte_count) / flowLivingTime / self.bw
            #print 'stat.match.in_port:', stat.match.in_port,'flow byte_count',stat.byte_count,'flowLivingTime:', flowLivingTime, 'flowDemand:', flowDemand, 'stat.match.scrIP:', stat.match.nw_src, 'stat.match.dstIP', stat.match.nw_dst
            src_name, src = self.IP2name_dpid(stat.match.nw_src)
            dst_name, dst = self.IP2name_dpid(stat.match.nw_dst)
            #print 'src_name:',src_name,'dst_name:', dst_name,'src_dpid:', src,'dst_dpid:', dst
            #print stat.match.nw_src, stat.match.nw_dst, stat.match.tp_src, stat.match.tp_dst
            if flowDemand > self.ratio:
                if src not in self.hostsList:
                    self.hostsList.append(src)
                    self.HostNameList.append({'node_name':src_name, 'dpid':src})
                if dst not in self.hostsList:
                    self.hostsList.append(dst)
                    self.HostNameList.append({'node_name':dst_name, 'dpid':dst})
                self.flows.append({ 'demand': flowDemand, 'converged':False, 'src': src, 'dst': dst, 'recLimited': False, 'match': stat.match})
        if self.statCntr == 0:
            #print "****flows processed, Estimating demands begins"
            self._demandEstimator()

    def _demandEstimator(self):
        '''estimate the actual flow demands here'''
        temp = self.flows
        temp = sorted(temp, key=lambda temp:temp['src'])
        self.flows = temp
        self.bwReservation = {}
        M, estFlows = demand_estimation(self.flows, sorted(self.hostsList))
        for flow in estFlows:
            demand = flow['demand']
            if demand >= self.ratio:
                self._GlobalBestFit(flow)

    def _GlobalBestFit(self,flow):
        '''do the Ashman global best fit here'''
        src_name = self.t.node_gen(dpid = flow['src']).name_str()
        dst_name = self.t.node_gen(dpid = flow['dst']).name_str()
        #print 'Global Best Fit for the elephant flow from ',src_name,'to', dst_name
        paths = self.r.routes(src_name,dst_name)
        #print 'all routes found for the big flow:\n',paths
        GBF_route = None
        deviation = 1.0;
        for path in paths:
            fitCheck = True
            residualCapacity = 1.0;
            for i in range(1,len(path)):
                fitCheck = False
                if self.bwReservation.has_key(path[i-1]) and self.bwReservation[path[i-1]].has_key(path[i]):
                    if self.bwReservation[path[i-1]][path[i]]['reserveDemand'] + flow['demand'] > 1 :
                        break
                    else:
                        #self.bwReservation[path[i-1]][path[i]]['reserveDemand'] += flow['demand']
                        fitCheck = True
                        if 1 - self.bwReservation[path[i-1]][path[i]]['reserveDemand'] - flow['demand'] < residualCapacity:
                            residualCapacity = 1 - self.bwReservation[path[i-1]][path[i]]['reserveDemand'] - flow['demand']
                else:
                    if (not self.bwReservation.has_key(path[i-1])):
                        self.bwReservation[path[i-1]]={}
                    self.bwReservation[path[i-1]][path[i]]={'reserveDemand':0}
                    fitCheck = True
            if fitCheck == True:
                if residualCapacity < deviation:
                    GBF_route = path
                    deviation = residualCapacity
        if GBF_route != None:
            for i in range(1,len(GBF_route)):
                self.bwReservation[GBF_route[i-1]][GBF_route[i]]['reserveDemand'] += flow['demand']
            #print "GBF route found:", GBF_route
            """install new GBF_path between source and destintaion"""
            self._install_customized_path(GBF_route,flow['match'])


    def _install_customized_path(self,customized_route, match):
        '''installing customized path here'''
        flow_match = match
        _route, match = self.matchDict[match.nw_src, match.nw_dst, match.tp_src, match.tp_dst]
        if _route != customized_route[1:-1] and not self.statMonitorLock.locked():
            #print "old route", _route
            #print "match info:", match.nw_src, match.nw_dst, match.tp_src, match.tp_dst
            self.statMonitorLock.acquire()
            ''' Install entries on route between two switches. '''
            route = customized_route[1:-1]
            #print"customized route to be installed between switches:", route

            for i, node in enumerate(route):
                node_dpid = self.t.node_gen(name = node).dpid
                if i < len(route) - 1:
                    next_node = route[i + 1]
                    out_port, next_in_port = self.t.port(node, next_node)
                else:
                    dpid_out, out_port = self.macTable[match.dl_dst]
                    #print 'out_dpid', dpid_out,self.t.node_gen(name = GFF_route[-1]).dpid
                    #print 'outPort', out_port
                self.switches[node_dpid].install(out_port, match,idle_timeout = 10)

            self.statMonitorLock.release()    
            self.matchDict[flow_match.nw_src, flow_match.nw_dst, flow_match.tp_src, flow_match.tp_dst] = (route, match)
        #print '_'*20


def launch(topo = None, routing = None, bw = None, ratio = None ):
    #print topo
    if not topo:
        raise Exception ("Please specify the topology")
    else: 
        t = buildTopo(topo)
    r = getRouting(routing, t)
    if bw == None:
        bw = 10.0 #Mb/s
        bw = float(bw/1000) #Gb/s
    else:
        bw = float(bw)/1000
    if ratio == None:
        ratio = 0.1
    core.registerNew(BFController, t, r, bw, ratio)
    log.info("** BFController is running")
 
