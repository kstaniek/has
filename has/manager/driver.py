# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
Generic Driver implementation. Will be used as a skeleton for further drivers for other devices.
TODO: Implement driver for iTach, Logitech Radio, CEC Library, Withings Scale, etc. 

"""


from has.utils.event import Event, Wait, Watcher
from has.utils.notification import Notification
from has.manager.hc2.hc2nodes import value_types
from has.manager.node import Node

import json
import time
from threading import Thread, Lock
import logging
logger = logging.getLogger('manager')


max_attempts = 0

class MsgQueueItem:
    MsgQueueCmd_SendMsg, \
    MsgQueueCmd_QueryStageComplete = range(2)
    
    
    def _init__(self):
        self.command = None
        self.msg = None
        self.params = None
        self.method = 'GET'
        self.query_stage = None
        self.retry = False
        self.node_id = 0


class Driver(Thread):
    """Generic driver class"""
    MsgQueue_Command, \
    MsgQueue_Query = range(2)
    
    def __init__(self, network):
        Thread.__init__(self)
        self.deamon = False
        self.network_id = network
        self.running = 0
        self.exit_event = Event("Exit")
        self.notifications = []
        self.notifications_event = Event("Notification")
        self.msg_queue = {}
        self.msg_queue[0] = []
        self.msg_queue[1] = []
        self.queue_event = {}
        self.queue_event[0] = Event("Command")
        self.queue_event[1] = Event("Query")
        self.send_lock = Lock()
        self.nodes = {}
        self.node_lock = Lock()
        self.all_nodes_queried = False
        
    def __repr__(self):
        return "Driver: %s" % self.network_id
    
    def stop(self):
        self.exit_event.set()
        
        self.notifications = []
        self.notifications_event.notify()
        
        if self.controller:
            self.controller.close()
            self.controller = None
        
    def start(self):
        Thread.start(self)
        
    def run(self):
        self.running = 1
        
    def get_network(self):
        return self.network_id
        
    def set_manager(self, manager):
        self.manager = manager
        
    def queue_notification(self, notification):  # TODO: Migrate to Queue
        self.notifications.insert(0, notification )
        self.notifications_event.set()
        
        
    def notify_watchers(self):
        while len(self.notifications) > 0:
            notification = self.notifications.pop()
            self.manager.notify_watchers(notification)
        self.notifications_event.clear()
            
    
    def init_node(self, node_id):
        raise NotImplemented
        return
    
    def check_completed_node_queries(self):
        logger.info("Driver.check_completed_node_queries: all_nodes_queried={0}".format(self.all_nodes_queried))
        if not self.all_nodes_queried:
            all_queried = True
            #logger.debug("Driver.check_completed_node_queries: all_nodes_queried={0}".format(self.all_nodes_queried))
            with self.node_lock:
                for node_id, node in self.nodes.items():
                    #logger.debug("Driver.check_completed_node_queries: Node {0}".format( node_id, node.query_stage ) )
                    if node.query_stage != Node.QueryStage_Complete:
                        logger.debug("Driver.check_completed_node_queries: Node {0}".format( node_id, node.query_stage ) )
                        all_queried = False
                        break
    
            if all_queried:
                logger.info("Driver.Node query processing complete")
                notification = Notification( Notification.Type_AllNodesQueried )
                self.queue_notification( notification )
                self.all_nodes_queried = True
                self.handle_all_nodes_queried()   # must be implemented by the specfic driver
               
    
    def send_query_stage_complete(self, node_id, stage):
        logger.debug("Driver.send_query_stage_complete: Node {0}: Stage {1}".format( node_id, stage ) )
        item = MsgQueueItem()
        item.command = MsgQueueItem.MsgQueueCmd_QueryStageComplete
        item.node_id = node_id
        item.query_stage = stage
        
        node = self.get_node( node_id )
        if node is not None:
            logger.debug("Node {0}: Queueing Query Stage Complete {1}".format( node_id, stage ) )
            with self.send_lock:
                self.msg_queue[Driver.MsgQueue_Query].insert(0, item)
                self.queue_event[Driver.MsgQueue_Query].set()    
            self.release_nodes()
            
    def handle_all_nodes_queried(self):
        raise NotImplemented
        return

# --------------- nodes --------------------
            
    def get_node(self, node_id):
        self.lock_nodes()
        try:
            return self.nodes[node_id]
        except:
            self.release_nodes()
            return None
    
    def get_node_unsafe(self, node_id):
        try:
            return self.nodes[node_id]
        except:
            return None
    
    def lock_nodes(self):
        self.node_lock.acquire()
    
    def release_nodes(self):
        self.node_lock.release()


    def get_node_type( self, node_id ):
        node = self.get_node( node_id )
        if node:
            res = node.node_type
            self.release_nodes()
            return res
        return "Unknown"
        
    def get_node_name( self, node_id ):
        node = self.get_node( node_id )
        if node:
            res = node.name
            self.release_nodes()
            return res
        return "Unknown"
        
    def get_node_description( self, node_id ):
        node = self.get_node( node_id )
        res = ""
        if node:
            res = node.description
            self.release_nodes()
        return res

    def get_node_location_name( self, node_id ):
        node = self.get_node( node_id )
        if node:
            res = node.location_name
            self.release_nodes()
            return res
        return "Unknown"

    def get_value(self, value_id):
        node = self.nodes[value_id.node_id]
        if node:
            return node.get_value( value_id )
        return None
