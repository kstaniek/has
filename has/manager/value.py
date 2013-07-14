# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
Value and ValueID class implementation

"""

#from  manager.manager import Manager
from datetime import datetime
from time import time
from has.utils.notification import Notification
from has.utils.utils import *

import logging
logger = logging.getLogger('manager')



class ValueID(object):
    
    def __init__(self, network_id, node_id, value_type):
        self.__id = ':'.join( ( str(network_id), str(node_id), str(value_type) ) )
    
    @property
    def    id(self):
        return self.__id
    
    @property    
    def network_id(self):
        return self.__id.split(':')[0]
    
    @property
    def node_id(self):
        return self.__id.split(':')[1]
    
    @property    
    def value_type(self):
        return self.__id.split(':')[2]
        
    def __eq__(self, other):
        if isinstance(other, ValueID):
            return self.__id == other.__id
        return NotImplemented
        
    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result
        
    def __str__(self):
        return str(self.__id)
        
    def __hash__(self):
        return hash(str(self))    
        
    def __iter__(self):
        yield self.__id
    
@timestamp('last_changed', ('set','update'))
class Value(object):
    def __init__(self, network_id, node_id, value_type, value, units = None):
        
        self._value_type = value_type
        self._value = str(value)
        self.__units = units
        self.__network_id = network_id
        self.__node_id = node_id
        self.__label = ""
        self.__read_only = True
        self.__id = ValueID( network_id, node_id, value_type )
        
    @property
    def value_id(self):
        return self.__id
    
    @property
    def network_id(self):
        return self.__network_id
    
    @property
    def is_read_only(self):
        return self.__read_only
        
    @is_read_only.setter
    def is_read_only(self, value):
        self.__read_only = value
    
    @property 
    def label(self):
        return self.__label
    
    @label.setter
    def label(self, value):
        self.__label = value

    @property    
    def value_type(self):
        return self._value_type
    
    @property    
    def location(self):
        return self.__location
    
    @location.setter
    def location(self, value):
        self.__location = value

    @property
    def units(self):
        return self.__units if self.__units is not None else "" 
    
    @units.setter
    def units(self, value):
        self.__units = value
    
    #@property
    #def timestamp(self):
        return self.__last_changed
    
    #@timestamp.setter
    #def timestamp(self, value = None):
    #    if value is None:
    #        self.__last_changed = datetime.today()
    #    else:
    #        if isinstance(value,int):
    #            value = datetime.fromtimestamp(value)
    #        self.__last_changed = value
            
    def get(self):
        #from  has.manager.manager import Manager  # to avoid import loop
        #driver = Manager.get_driver( self.__network_id )
        #node = driver.get_node_unsafe( self.__node_id )
        #node.query_node_info()
        return str(self._value)
        
    def get_as_string(self):
        from  has.manager.manager import Manager  # to avoid import loop
        driver = Manager.get_driver( self.__network_id )
        node = driver.get_node_unsafe( self.__node_id )
        result = "{0}{1}".format(self._value, self.__units)
        return result

        
    def set(self, value):
        if( self.is_read_only ):
            logger.debug("Value:set ValueType:%s is read only" % self.value_type)
            return False
        
        from has.manager.manager import Manager
        driver = Manager.get_driver( self.__network_id ) 
        if driver is not None:
            node = driver.get_node_unsafe( self.__node_id )
            if node is not None:
                node.set_value( self, value )
                return True

        return False
    
    def on_value_refresh(self, value):
        if self._value != value:
            self.update(value)
            
    def update(self, value):
        self._value = str(value)
        notification = Notification( Notification.Type_ValueChanged )
        notification.node_id = self.__node_id
        notification.network_id = self.__network_id
        notification.value_id = self.__id
        from has.manager.manager import Manager
        driver = Manager.get_driver( self.__network_id )
        driver.queue_notification( notification )
        
        
    
class TimeStampValue(Value):
    def get_as_string(self):
        try:
            timestamp = int(self._value)
            result = datetime.fromtimestamp(timestamp)
        except ValueError:
            result = "unknown"
        return result
        
class OpenCloseValue(Value):
    def get_as_string(self):
        return "open" if int(self._value) == 1 else "close"

class OnOffValue(Value):
    def get_as_string(self):
        return "on" if int(self._value) == 1 else "off"

    