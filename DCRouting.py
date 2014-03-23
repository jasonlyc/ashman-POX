''' Simple hashed-based routing

@author: Milad Sharif (msharif@stanford.edu)
'''

import logging
from copy import copy



class Routing(object):
    '''Base class for data center network routing.

    Routing engines must implement the get_route() method.
    '''

    def __init__(self, topo):
        '''Create Routing object.

        @param topo Topo object from Net parent
        '''
        self.topo = topo

    def get_route(self, src, dst, hash_):
        '''Return flow path.

        @param src source host
        @param dst destination host
        @param hash_ hash value

        @return flow_path list of DPIDs to traverse (including hosts)
        '''
        raise NotImplementedError


    def routes(self, src, dst):
        ''' Return list of paths
        
        Only works for Fat-Tree topology

        @ param src source host
        @ param dst destination host

        @ return list of DPIDs (including inputs) 
        '''  
        
        complete_paths = [] # List of complete dpid routes
        
        src_paths = { src : [[src]] }
        dst_paths = { dst : [[dst]] } 
    
        dst_layer = self.topo.layer(dst)
        src_layer = self.topo.layer(src)
        
        lower_layer = src_layer
        if dst_layer > src_layer:
            lower_layer = dst_layer
        

        for front_layer in range(lower_layer-1, -1, -1):
            if src_layer > front_layer:
            # expand src frontier
                new_src_paths = {}
                for node in sorted(src_paths):
                    path_list = src_paths[node]
                    for path in path_list:
                        last_node = path[-1]
                        for frontier_node in self.topo.upper_nodes(last_node):
                            new_src_paths[frontier_node] = [path + [frontier_node]]

                            if frontier_node in dst_paths:
                                dst_path_list = dst_paths[frontier_node]
                                for dst_path in dst_path_list:
                                    dst_path_copy = copy ( dst_path )
                                    dst_path_copy.reverse()
                                    complete_paths.append( path + dst_path_copy)
                src_paths = new_src_paths
            
            if dst_layer > front_layer:
            # expand dst frontier
                new_dst_paths = {}
                for node in sorted(dst_paths):        
                    path_list = dst_paths[node]
                    for path in path_list:
                        last_node = path[-1]
                        for frontier_node in self.topo.upper_nodes(last_node):
                            new_dst_paths[frontier_node] = [ path + [frontier_node]]
                        
                            if frontier_node in src_paths:
                                src_path_list = src_paths[frontier_node]
                                dst_path_copy = copy( path )
                                dst_path_copy.reverse()
                                for src_path in src_path_list:
                                    complete_paths.append( src_path + dst_path_copy)
            
                dst_paths = new_dst_paths

            if complete_paths:
                return complete_paths


class HashedRouting(Routing):
    ''' Hashed routing '''

    def __init__(self, topo):
        self.topo = topo

    def get_route(self, src, dst, hash_):
        ''' Return flow path. '''
        
        if src == dst:
            return [src]
    
        paths = self.routes(src,dst)
        if paths:
            choice = hash_ % len(paths)
            path = sorted(paths)[choice]
            return path

