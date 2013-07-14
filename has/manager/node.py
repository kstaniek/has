# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
Generic Z-Wave Node class implementation

"""
import logging

from has.manager.value import Value, ValueID
from has.utils.notification import Notification

import logging
logger = logging.getLogger('manager')


class Node(object):
    QueryStage_NodeInfo, \
    QueryStage_NodeValues, \
    QueryStage_Complete, \
    QueryStage_None = range(4)
    
    def __init__(self, network_id, node_id):
        self._network_id = network_id
        self._node_id = node_id
        self._query_pending = False
        self._node_info = None
        self._node_info_received = False
        self._values_info_received = False
        self.__query_stage = Node.QueryStage_None
        
        """
        Private attributes
        """
        self.__values = []
        self.__query_retries = 0
        self.__add_QSC = False

        
    @property    
    def driver(self):
        from has.manager.manager import Manager
        driver = Manager.get_driver( self._network_id )
        return driver
        
    @property
    def name(self):
        raise NotImplemented
        return ""    
    

    @property
    def location(self):
        raise NotImplemented
        return ""

    @property
    def location_name(self):
        raise NotImplemented
        return ""
        
    @property
    def node_type(self):
        raise NotImplemented
        return "unknown"
    
    @property 
    def units(self):   #### TODO: handle missing units
        raise NotImplemented
        return ""
    
            
    @property
    def description(self):
        raise NotImplemented
        return None
            
    
    @property
    def is_dead(self):
        raise NotImplemented
        return None
        
    @property
    def is_light(self):
        raise NotImplemented
        return None
        
    @property
    def is_battery_operated(self):
        raise NotImplemented
        return None

    
    def advance_queries(self):
        raise NotImplemented
        return None
            
    @property    
    def query_stage(self):
        return self.__query_stage
    
    def set_query_stage(self, stage, advance = True):
        #logger.debug("Node %s: query_stage: %s" % (self._node_id, stage))
        if stage < self.__query_stage:
            self.__query_stage = stage
        
        self._query_pending = False
        
        if advance:
            #logger.debug("Node %s: query_stage: Calling advance_queries: stage %s" % (self._node_id, self.query_stage))
            self.advance_queries()

    def query_stage_complete(self, stage):
        if stage != self.__query_stage:
            return
        if self.__query_stage != Node.QueryStage_Complete:
            self._query_pending = False
            self.__query_stage = self.__query_stage + 1
            self.__query_retries = 0

    def query_node_info(self):
        raise NotImplemented
        return None
    
    def advance_queries(self):
        self.add_QSC = False
        logger.debug("Node {0}: queryPending={1} queryStage={2}".format(self._node_id, self._query_pending, self.query_stage ) )
        while not self._query_pending:
            
            if self.query_stage == Node.QueryStage_None:
                logger.debug("Node {0}: Query Stage None".format(self._node_id) )
                self.__query_stage = Node.QueryStage_NodeInfo
                #logger.debug("advance_queries: Node: {0} Move to stage NodeInfo".format(self._node_id))
                self.query_retries = 0

            
            elif self.query_stage == Node.QueryStage_NodeInfo:
                logger.debug("Node {0}: Query Stage NodeInfo".format(self._node_id) )
                if not self._node_info_received:
                    self.query_node_info()
                    #logger.info("advance_queries: Node: {0} Query command sent %s".format(self._node_id))
                    self._query_pending = True
                    self.add_QSC = True
                else:
                    #logger.debug("advance_queries: Node: {0} Move to stage NodeValues".format(self._node_id))
                    self.__query_stage = Node.QueryStage_NodeValues
                    self.query_retries = 0

            
            elif self.query_stage == Node.QueryStage_NodeValues:
                assert self._node_info_received == True, "Advanced to query node values but not info not received"
                logger.debug("Node {0}: Query Stage NodeValues".format(self._node_id) )
                if not self._values_info_received:
                    logger.debug("advance_queries: Node: {0} Update values info command send".format(self._node_id) )
                    self.update_values_info()
                    self._query_pending = True
                    self.add_QSC = True
                else:
                    #logger.debug("advance_queries: Node: {0} Move to stage Complete".format(self._node_id))
                    self.update_values_info()
                    self.__query_stage = Node.QueryStage_Complete
                    self.query_retries = 0
                                
            elif self.query_stage == Node.QueryStage_Complete:
                logger.info("Node {0}: All Queries Complete".format(self._node_id) )
                notification = Notification( Notification.Type_NodeQueriesComplete )
                notification.node_id = self._node_id
                notification.network_id = self._network_id
                self.driver.queue_notification( notification )
                self.driver.check_completed_node_queries()
                return

    
        if self.add_QSC:
            #logger.debug("advance_queries: Sending query stage complete: {0}".format(self._node_id))
            self.driver.send_query_stage_complete( self._node_id, self.query_stage )
            return

    def update_node_info(self, node_info):
        logger.debug("Node:update_node_info: Node {0}:".format( self._node_id ) )
        assert node_info is not None, "Update node info with 'None' value"
        changes = set()
        if self._node_info is not None:
            set_current, set_past = set(node_info.keys()), set(self._node_info.keys())
            intersect = set_current.intersection(set_past)  
            changes = set(o for o in intersect if self._node_info[o] != node_info[o])
                    
        self._node_info = node_info
        self._node_info_received = True
        self._values_info_received = True  
        
        if changes:
            notification = Notification( Notification.Type_NodeChanged )
            notification.node_id = self._node_id
            notification.network_id = self._network_id
            self.driver.queue_notification( notification ) 
            self.set_query_stage( Node.QueryStage_NodeInfo )
    
    def create_value_id(self, value_type):
        return ValueID( self._network_id, self._node_id, value_type)
        
    def add_value(self, value_obj):
        logger.debug("Node:add_value: ValueID:%s" % value_obj.value_id)
        self.__values.insert(0, value_obj)
        notification = Notification( Notification.Type_ValueAdded )
        notification.node_id = self._node_id
        notification.network_id = self._network_id
        notification.value_id = value_obj.value_id
        self.driver.queue_notification( notification )
    
    def update_value(self, value_type, value):
        logger.debug("Node:update_value: ValueType:%s" % value_type)
        value_id = self.create_value_id( value_type )
        value_obj = self.get_value( value_id )
        if value_obj:
            value_obj.on_value_refresh( value ) 
        else:
            #assert False, "Update of no
            self.query_node_info()
            #self.create_value(value_type, value, "") #TODO: What about units?????
            

    def get_value(self, value_id):
        """
        Returns the Value instance belonging to the node or None if not extis.
        
        Params:
            value_id:   ValueID object
        """
            
        for value_obj in self.__values:
            if value_obj.value_id == value_id:
                return value_obj
        return None
        
    def set_value(self, value_id, value):  #TODO: Add variable set  - delegate to Value obj - virtualize
        raise NotImplemented
        return None
    