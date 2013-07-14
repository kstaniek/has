# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
HC2Device and HC2Variable class implementation

"""
import logging

#import has.manager
from has.manager.node import Node
from has.manager.value import Value, OnOffValue, OpenCloseValue,TimeStampValue


value_types = ( "sunriseHour", "sunsetHour", "dead", "valueSensor", "valueMeter", "value", 
                "batteryLevel", "armed", "lastBreached", "color", "currentProgram",
                "lastColorSet", "lastUsedPrograms", "modified","created", "nextDrenching", "mode" )
value_types_rw = ( "value", "armed" )

import logging
logger = logging.getLogger('manager')
import json


class HC2Device(Node):

    @property
    def name(self):
        if self._node_info is not None:
            try:
                return self._node_info['name']
            except:
                pass
        return ""    
    

    @property
    def location(self):
        """ Physical node location id property """
        if self._node_info is not None:
            try:
                return self._node_info['roomID']
            except:
                return None        #TODO: Ignorance is not bliss
        return ""

    @property
    def location_name(self):
        """ Physical node location name """
        res = ""
        if self._node_info is not None:
            try:
                return self.driver.get_location_name( self.location )
            except Excepton as e:
                return "" #TODO: Ignorance is not bliss
        return ""
        
    @property
    def node_type(self):
        if self._node_info is not None:
            try:
                return self._node_info['type']
            except Exception as e:
                print("Exception in HC2Device:node_type: %s"  % e )
                pass
        return None
    
    @property 
    def units(self):   #### TODO: handle missing units
        if self._node_info is not None:
            try:
                properties = self._node_info['properties']
                return properties['unit']
            except:
                pass
        return ""
    
    @units.setter
    def units(self, units):
        """ Value units text """
        if self.__node_info is not None:
            try:
                self._node_info['properties']['unit'] = units
            except:
                pass
    
    def __getattr__(self, name):
        try:
            attr = self._node_info[name]
            if isinstance( attr, dict):
                return self
            else:
                return attr            
        except:
            pass
            #logger.debug("Node:__getattr__: missing or invalid attribute:  %s" % name)
            #print("Node:__getattr__: missing or invalid attribute:  %s" % name)
            
        try:
            return self._node_info['properties'][name]
        except:
            raise AttributeError  # Used by hasattrib
            
            
    @property
    def description(self):
        try:
            properties = self._node_info['properties']
            return properties['userDescription'] if properties['userDescription'] is not None else ""
        except:
            logger.debug("Node:description: missing userDescription")
            return ""
            
    
    @property
    def is_dead(self):
        res = False
        if self._node_info is not None:
            try:
                properties = self._node_info['properties']
                if properties['dead'] != "0":
                    res = True
            except:
                res = False #TODO: Ignorance is not bliss
        return res
        
    @property
    def is_light(self):
        res = False
        if self._node_info is not None:
            try:
                properties = self._node_info['properties']
                #print "node %s, deviceControlType %s" % (self.id, self.properties.deviceControlType)
                if properties['deviceControlType'] in ("2", "23"):
                    res = True
            except:
                res = False
        
        return res    
    
    @property
    def is_battery_operated(self):
        res = False
        if self._node_info is not None:
            try:
                properties = self._node_info['properties']
                if properties['isBatteryOperated'] == '1':
                    res = True
            except:
                res = False
        return res    
    
    
    def query_node_info(self):
        logger.info("Node {0}: Query for Device Info".format( self._node_id ) )
        self.driver.send_msg(0, "GET", "/api/devices?id={0}".format( self._node_id ) ) # command queue
            

    def update_values_info(self):
        logger.debug("Node {0}: values_info_received={1}".format( self._node_id, self._values_info_received ) )
        if self._node_info_received:
            fix_units = '' # patch until fibaro fix it TODO: update getter for unists
            if self.units == "": 
                if self.node_type == 'dimmable_light':
                    fix_units = "%"
                elif self.node_type == 'thermostat_setpoint':
                    fix_units = "C"
            for attr in value_types:
                if hasattr(self, attr):
                    units = ''    # reset
                    if attr == 'valueMeter':
                        units = self.unitMeter
                    elif attr == 'valueSensor':
                        units = self.unitSensor
                    elif attr == 'value':
                        units = self.units if self.units != "" else fix_units
                    
                    
                    value_id = self.create_value_id( attr )
                    if self.get_value( value_id ) is not None:
                        logger.debug("Node {0}: Name {1} update value {2}".format( self._node_id, self.name, attr) )
                        self.update_value(attr, getattr(self, attr) )
                        
                    else: 
                        logger.debug("Node {0}: Name {1} create value {2}".format( self._node_id, self.name, attr) )
                        self.create_value( attr, getattr(self, attr), units )
                    
        
        self._values_info_received = True  
       
        
    def set_value(self, value_id, value):  #TODO: Add variable set  - delegate to Value obj - virtualize
        assert self.node_type != "unknown", "Unknown device type"
        send = False
        value_type = value_id.value_type
        if value_type == "value":
            command = "/api/callAction?deviceID={0}&name=setValue&arg1={1}".format( self._node_id, value )
            send = True
    
        elif value_type == "armed":
            command = "/api/callAction?deviceID={0}&name=setArmed&arg1={1}".format( self._node_id, value )
            send = True
        
        if send:
            self.driver.send_msg(0, 'GET', command ) #Driver.MsgQueue_Command
        



    def create_value(self, value_type, value, units=""): 
        logger.debug("Node {0}: Create value: {1}".format( self._node_id, value_type ) )
        if value_type in ("lastBreached","modified","created"):
            value_obj = TimeStampValue( self._network_id, self._node_id, value_type, str(value), "")
        elif value_type == 'value':
            if self.node_type == "binary_light":
                value_obj = OnOffValue( self._network_id, self._node_id, value_type, str(value), "")
            elif self.node_type in ("door_sensor","window_sensor"):
                value_obj = OpenCloseValue( self._network_id, self._node_id, value_type, str(value), "")
            else:
                value_obj = Value( self._network_id, self._node_id, value_type, str(value), units )
        else:        
            value_obj = Value( self._network_id, self._node_id, value_type, str(value), units)
        
        ro = getattr(self, 'readOnly', True)
        
        if (value_type in value_types_rw) or (ro is False):
            value_obj.is_read_only = False
                    
        logger.debug("Node {0}: Adding value: {1}".format( self._node_id, value_type ) )
        self.add_value( value_obj )
            
        

            

#------------------------------- VariableNode
class HC2Variable(Node):
    
    def __init__(self, network_id, node_id):
        super().__init__(network_id, node_id)
        self.__units == ""
        

    @property
    def name(self):
        if self._node_info is not None:
            try:
                return self._node_info['name']
            except:
                pass
        return ""
    
    @property
    def location(self):
        return ""

    @property
    def location_name(self):
        return self._network_id   # Variables are located on network controller
        
    @property
    def node_type(self):
        return "variable"
    
    @property 
    def units(self):
        return self.__units
    
    @units.setter
    def units(self, units):
        self.__units = units    
    
    def __getattr__(self, name):
        try:
            attr = self._node_info[name]
            if type(attr).__name__=='dict':  #TODO: isinstance
                return self
            else:
                return attr            
        except:
            pass
            #logger.debug("Node:__getattr__: missing or invalid attribute:  %s" % name)
            #print("Node:__getattr__: missing or invalid attribute:  %s" % (name))
            #return super().__getattr__(name)
                        
            
    @property
    def description(self):
        return "variable"
                
    @property
    def is_dead(self):
        return False
                
    @property
    def is_light(self):
        return False    
    @property
    def is_battery_operated(self):
        return False
        
    def query_node_info(self):
        logger.info("Node {0}: Query for Variable Info".format( self._node_id ) )
        self.driver.send_msg(0, 'GET', "/api/globalVariables?name=%s" % self._node_id) # command queue
        

    def update_values_info(self):
        logger.debug("Node {0}: values_info_received={1}".format( self._node_id, self._values_info_received ) )
        if self._node_info_received:
            self._node_info['type'] = "variable"
            self._node_info['unit'] = ""
            value_id = self.create_value_id( 'value' )
            if self.get_value( value_id ) is not None:
                logger.debug("Node {0}: Name {1} update value {2}".format( self._node_id, self.name, 'value') )
                self.update_value( 'value', str(self._node_info['value'] ) )
            else: 
                logger.debug("Node {0}: Name {1} create value {2}".format( self._node_id, self.name, 'value') )
                self.create_value( 'value', str(self._node_info['value'] ) )
            
               
        self._values_info_received = True 
      
    def set_value(self, value_id, value):
        assert self.node_type == "variable", "Expected node_type to be variable"
        send = False
        value_type = value_id.value_type
        command = "/api/globalVariables"
        params = {}
        params['name'] = self._node_id
        params[value_type] = value
        params = json.dumps(params)
        self.driver.send_msg(0, 'PUT', command, params) #Driver.MsgQueue_Command
        #self.driver.send_msg(0, "/api/globalVariables?name=%s" % self._node_id) # command queue
        
        
    def create_value(self, value_type, value, units=""):
        logger.debug("Node:create_value: Node {0}: value: {1}".format( self._node_id, value_type ) )
        value_obj = Value( self._network_id, self._node_id, value_type, str(value), units)
        #value_obj.is_read_only = False  ## TODO: check the variable property
        try:
            value_obj.is_read_only = self._node_info['readOnly']
        except KeyError as e:
            logger.debug("Node:create_value : missing readOnly attribure in %s" % ( self._node_id ) ) 
        self.add_value( value_obj )
    
    