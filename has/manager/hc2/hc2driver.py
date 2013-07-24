# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
Generic Driver implementation and specific HC2Driver 

"""
#from manager.driver import Driver, MsgQueueItem
from has.manager.node import Node
from has.utils.notification import Notification
from has.utils.event import Wait
from has.manager.driver import MsgQueueItem
from has.manager.driver import Driver
from has.manager.hc2.hc2controller import HC2Controller
from has.manager.hc2.hc2nodes import HC2Device, HC2Variable, value_types

import json

""""
just for test import time
"""
import time


import logging
logger = logging.getLogger('manager')

max_attempts = 0    

class HC2Driver(Driver):
    """Driver for HC2"""
    
    def __init__(self, network, username, password, ip, port, remote=False, remote_server=None, remote_username=None, remote_password=None ):
        super().__init__(network)
        
        #self.url = "http://" + ip + ":" + str( port )
        self.controller = None
        self.username = username
        self.password = password
        self.host = ip
        self.port = port
        self.running = False
        self.wait_objects = {}
        self.current_message = None
        
        self.remote = remote
        self.remote_server  = remote_server
        self.remote_username = remote_username
        self.remote_password = remote_password
        
        self.all_devices_queried = False
        self.all_variables_queried = False
        
        self.__devices = set()
        self.__variables = set()
        
        self.locations = {}
        
        self.__handlers = dict (  api_refreshStates = self.__handle_refresh_states,
                                api_settings_info = self.__handle_settings_info_response,
                                api_rooms = self.__handle_locations_response,
                                api_devices = self.__handle_devices_response,
                                api_globalVariables = self.__handle_global_variables_response,
                                api_callAction = self.__handle_call_action_response,
                                error = self.__handle_error_response,
                                default = self.__handle_default_response)
        
    
    def init(self, attempt):
        logger.info("HC2Driver.init(): Attempt {0}".format( attempt ) )
        if self.controller == None:
            self.controller = HC2Controller( self.host, self.username, self.password, self.port, 
                                            self.remote, self.remote_server, self.remote_username, self.remote_password) 
            logger.info("HC2Driver.Init: New controller created")
        
        if not self.controller.open(self.network_id):
            logger.error("HC2Driver.init(): Opening new controller failed")
            self.controller.running = False
            self.controller = None
            return False
        return True        
            
    def run(self):
        logger.info("HC2Driver.run")
        attempt = 0
        while True:
            self.wait_objects[0] = None
            self.wait_objects[1] = None
            self.wait_objects[2] = None
            self.wait_objects[3] = None
            self.all_nodes_queried = False
                
            if self.init(attempt):
                self.running = 1
                self.attempt = 0
                self.wait_objects[0] = self.exit_event
                self.wait_objects[1] = self.notifications_event
                self.wait_objects[2] = self.controller
                self.wait_objects[3] = self.queue_event[0]
                self.wait_objects[4] = self.queue_event[1]
                
                
                #objects_number = 5
                logger.info("HC2Driver.run: Running")
                while self.running:
                    logger.debug("HC2Driver.run: Waiting for event")
                    res = Wait.multiple( self.wait_objects )
                    logger.debug("HC2Driver.run: Event: {0}".format( res ) )
                    if res == 0:
                        logger.debug("HC2Driver.run: Exit Event")
                        #self.Stop()
                        return
                    elif res == 1:
                        logger.debug("HC2Driver.run: Notification Event")
                        self.notify_watchers()
                    elif res == 2:
                        logger.debug("HC2Driver.run: Data Received")
                        self.read_msg()
                    elif res == -1:
                        logger.debug("HC2Driver.run: res = -1")
                        assert res != -1, "Wait.Multiple returned res = -1"
                        
                    else:
                        logger.debug("HC2Driver.run: Message Queue Event: {0}".format(res -3))
                        self.write_next_msg(res - 3)
                    
        
            else:
                attempt += 1
                logger.debug("HC2Driver.run: Max attempts: {0}".format( max_attempts ) )
                if max_attempts > 0 and ( attempt >= max_attempts):
                    self.manager.set_driver_ready(self, False)
                    self.notify_watchers()
                    logger.error("HC2Driver.run: Max attempts exceeded")
                    break
                
                if attempt < 10:
                    logger.debug( "HC2Driver.run: Connection timeout. Waiting 5 second" )

                else:
                    logger.debug( "HC2Driver.run: Connection timeout. Waiting 30 second" )
                    res = Wait.single( self.exit_event, 30)
                    if res == 0:
                        logger.error("HC2Driver.run: Exit signaled")
                        return                
    
    def send_msg(self, queue, method, message, params=None):
        """
        Quiging the message to the message queue for further sending to the controller
        """
        item = MsgQueueItem()
        
        item.command = MsgQueueItem.MsgQueueCmd_SendMsg
        item.msg = message
        item.params = params
        item.method = method
        logger.debug( "HC2Driver.SendMsg: Queueing: {0}:{1}:{2}".format( method, message, params ) )
        with self.send_lock:
            self.msg_queue[queue].insert(0, item)
            self.queue_event[queue].set()
        logger.debug( "HC2Driver.SendMsg: Queued: {0}".format( message ) )

    
    
    def write_next_msg(self, queue):
        logger.debug( "HC2Driver.write_next_msg: queue: {0}".format( queue ) )
        self.send_lock.acquire()
        
        item = self.msg_queue[queue].pop()
        logger.debug( "HC2Driver.write_next_msg: item: {0}".format( item.command ) )
        
        if MsgQueueItem.MsgQueueCmd_SendMsg == item.command:
            self.current_message = item.msg
            self.current_params = item.params
            self.current_method = item.method
            if len( self.msg_queue[queue] ) == 0:
                self.queue_event[queue].clear()
            self.send_lock.release()        
            return self.write_msg();
                
        if MsgQueueItem.MsgQueueCmd_QueryStageComplete == item.command:
            self.current_message = None
            stage = item.query_stage
            if len( self.msg_queue[queue] ) == 0:
                self.queue_event[queue].clear()
            self.send_lock.release()
            
            node = self.get_node_unsafe( item.node_id )
            if node is not None:
                logger.info("Node {0}: Query Stage Complete ({1})".format( item.node_id, item.query_stage ) )
                node.query_stage_complete( stage )
                node.advance_queries()
                return True
    
        self.send_lock.release()
        
        return False
    
    
    def write_msg(self):
        """
        Write message to the controller
        
        current message is stored in:
            self.current_method
            self.current_message
            self.current_params
        """    
        if self.controller.send(self.current_method, self.current_message, self.current_params):
            return True
        else:
            return False
    
    
    def read_msg(self):
        """
        Read the message from the comntroller and call the handler
        """
        command, parameters, response  = self.controller.receive()
        try:
            return self.__handlers[command](command, parameters, response)
        except KeyError:
            logger.error( "HC2Driver: Unhandled response: command={0}, parameters={1}, response={2}".format( command, parameters, response ) )
            return
    
    def __handle_default_response( self, command, parameters, response ):
        logger.error( "HC2Driver: Unhandled command: command={0}, parameters={1}, response={2}".format( command, parameters, response ) )
        return
                
    def __handle_error_response( self, command, parameters, response ):
        logger.error( "HC2Driver: Controller error reported. Reinitializing the controller" )
        self.running = False
        del self.notifications
        self.notifications = []
        self.controller.running = False
        self.controller.close()
        del self.controller
        self.controller = None
        return
    
    def __handle_devices_response( self, command, parameters, response ):
        logger.debug( "HC2Driver.handle_devices_response: {0}".format( parameters ) )
        try:
            nodes = json.loads( response )
        except:
            logger.error( "HC2Driver.handle_devices_response: response is not formated as json: {0}".format( response) )
            return
        
        if isinstance(nodes, dict):
            """
            response contains single device information
            """
            nodes = [nodes]
            all_nodes = False
        else:
            """
            response contains all devices information
            """
            all_nodes = True   
            
        new_nodes = set()    
        for node_info in nodes:
            node_id = str(node_info['id'])
            
            if all_nodes:
                new_nodes.add(node_id)
            
            if node_id in self.__devices:
                logger.debug('Node {0}: Updated'.format(node_id)) 
                self.nodes[node_id].update_node_info(node_info)                
            else:
                logger.debug('Node {0}: Added'.format(node_id)) 
                self.lock_nodes()
                self.__devices.add( node_id )
                self.nodes[node_id] = HC2Device(self.network_id, node_id)                
                self.nodes[node_id].update_node_info(node_info)
                self.release_nodes()
                notification = Notification( Notification.Type_NodeAdded )
                notification.node_id = node_id
                notification.network_id = self.network_id
                self.queue_notification( notification )
            
            #self.nodes[node_id].set_query_stage( Node.QueryStage_NodeValues, True )
            self.send_query_stage_complete(node_id, Node.QueryStage_NodeInfo )
        
        if all_nodes:
            missing_nodes = self.__devices - new_nodes
            for node_id in missing_nodes:
                logger.debug('Node {0}: Removed'.format(node_id)) 
                self.lock_nodes()
                del self.nodes[node_id]
                self.release_nodes()
                notification = Notification( Notification.Type_NodeRemoved )
                notification.node_id = node_id
                notification.network_id = self.network_id
                self.queue_notification( notification )
        return
    
    def __handle_global_variables_response( self, command, parameters, response ):
        try:
            nodes = json.loads( response )
        except:
            logger.error( "HC2Driver.handle_global_variables_response: response is not formated as json: {0}".format(response) )
            return
            
        if isinstance(nodes, dict):
            """
            response contains single device information
            """
            nodes = [nodes]
            all_nodes = False
        else:
            """
            response contains all devices information
            """
            all_nodes = True   
            
        new_nodes = set()    
        for node_info in nodes:
            node_id = str(node_info['name'])
            if all_nodes:
                new_nodes.add(node_id)
            
            if node_id in self.__variables:
                logger.debug('Variable {0}: Updated'.format(node_id)) 
                self.nodes[node_id].update_node_info(node_info)
            else:
                logger.debug('Variable {0}: Added'.format(node_id)) 
                self.lock_nodes()
                self.__variables.add( node_id )
                self.nodes[node_id] = HC2Variable(self.network_id, node_id)                
                self.nodes[node_id].update_node_info(node_info)
                self.release_nodes()
                notification = Notification( Notification.Type_NodeAdded )
                notification.node_id = node_id
                notification.network_id = self.network_id
                self.queue_notification( notification )
            self.send_query_stage_complete(node_id, Node.QueryStage_NodeInfo )
        
        if all_nodes:
            missing_nodes = self.__variables - new_nodes
            for node_id in missing_nodes:
                logger.debug('Variable {0}: Removed'.format(node_id)) 
                self.lock_nodes()
                del self.nodes[node_id]
                self.release_nodes()
                notification = Notification( Notification.Type_NodeRemoved )
                notification.node_id = node_id
                notification.network_id = self.network_id
                self.queue_notification( notification )
        return
        
        
        
    def __handle_locations_response( self, command, parameters, response ):
        logger.debug("HC2Driver.handle_locations: response={0}".format( response ) )
        try:
            self.locations = json.loads( response )
        except:
            logger.error( "HC2Driver.__handle_locations: response is not formated as json: {0}".format( response) )
            return
            
            
    def __handle_refresh_states( self, command, parameters, response ):
        logger.debug("HC2Driver.handle_refresh_states: response={0}".format(response) )
        """
        """
        if response == "": ### DONT LIKE IT
            return
        try:
            content = json.loads( response )
        except:
            logger.error( "HC2Driver.__handle_refresh_states: response is not formated as json: {0}".format( response) )
            return
            
        status = content['status']
        if status == "IDLE":
            timestamp = content['timestamp']
            if 'changes' in content.keys():
                changes = content['changes']
                for change in changes:
                    if 'id' in change.keys():
                        node_id = str(change['id'])
                        logger.debug("Node {0}: Refresh".format( node_id) )
                        if 'log' in change.keys():
                            if change['log'].startswith('{'):  # TODO: VARIABLE HANDLING
                                try:
                                    log = json.loads( change['log'] )
                                    variables = log['var']
                            
                                except Exception as err:
                                    logger.error("HC2Driver:handle_refresh_states Exception: {0}".format( err ) )
                                    logger.error("HC2Driver:handle_refresh_states Change: {0}".format( change ) )
                                    logger.error("HC2Driver:handle_refresh_states Log: {0}".format( log ) )
                                    return
                                
                                for name in variables:
                                    node = self.get_node(name)
                                    if node is not None:
                                        if node._node_info_received:
                                            node.update_value( 'value', str(variables[name]) ) 
                                        else:
                                            logger.debug("Node {0}: Refresh but node info not received. Refresh skipped".format( name ) )
                                
                                        self.release_nodes()
                                    else:
                                        logger.debug("Node {0}: Refresh for non existing variable".format( name ) )
                                        self.send_msg( Driver.MsgQueue_Command, "GET", "/api/globalVariables?name={0}".format( name ) )
                                    
                        for value_type in value_types:
                            if value_type in change.keys():
                                node = self.get_node(node_id)
                                if node is not None: 
                                    if node._node_info_received:
                                        node.update_value( value_type, str(change[value_type]) )
                                    else:
                                        logger.debug("Node {0}: Refresh but node info not received. Refresh skipped" % node_id)
                                    self.release_nodes()
                                else:
                                    logger.debug("Node {0}: Refresh for non existing node".format( node_id) )
                                    self.send_msg( Driver.MsgQueue_Command,  "GET", "/api/devices?id={0}".format(node_id))
                                    #self.init_node(node_id)
            
        elif status in ['ZWAVE_LEARN_MODE_ADDING','ZWAVE_LEARN_MODE_REMOVING']:
            logger.debug("HC2Driver.handle_refresh_states: {0}".format( status ) )
        else:
            logger.error("HC2Driver.handle_refresh_states: Unhandler status")
            logger.error("HC2Driver:handle_refresh_states: {0}".format( content ) )
            logger.error("HC2Driver:handle_refresh_states: {0}".format( response ) )
        
        return
    
    def __handle_settings_info_response( self, command, parameters, response ):
        logger.debug( "HC2Driver.HandleSettingsInfoResponse: response={0}".format( response ) )
        try:
            info = json.loads( response )
            self.serial_number = info['serialNumber']
            self.mac = info['mac']
            self.soft_version = info['softVersion']
            self.zwave_version = info['zwaveVersion']
            self.default_language = info['defaultLanguage']
        except:
            logger.error( "HC2Driver.handle_setings info: response is not formated as json: {0}".format( response ) )
            return
        
        if self.network_id != self.serial_number:
            logger.error("HC2Driver:Serial number mismatch: Configured:{0}, Received:{1}".format( self.network_id, self.serial_number) )
            self.manager.set_driver_ready(self, False)    
            return
            
        
        self.manager.set_driver_ready(self, True)
        self.request_initial_data()
        
    def __handle_call_action_response( self, command, parameters, response ):
        logger.debug( "HC2Driver.handle_call_action_response: Call action executed")   
        return 
    
    
    def handle_all_nodes_queried(self):
        logger.debug("HC2Driver.handle_all_nodes_queried. Requesting: /api/refreshStates")
        self.send_msg( Driver.MsgQueue_Command,  "GET", "/api/refreshStates")

    
    def request_initial_data(self):
        logger.debug("HC2Driver.get_initial_data: /api/rooms")
        self.send_msg( Driver.MsgQueue_Command,  "GET", "/api/rooms" )
        
        logger.debug("HC2Driver.get_initial_data: /api/devices")
        self.send_msg( Driver.MsgQueue_Command,  "GET", "/api/devices")
        
        logger.debug("HC2Driver.get_initial_data: /api/globalVariables")
        self.send_msg( Driver.MsgQueue_Command,  "GET", "/api/globalVariables")
            
    def get_location_name(self, location_id):
        if location_id == 0:
            return 'Unassigned'
        for location in self.locations:
            if location['id'] == location_id:
                return location['name']
        return self.serial_number
        
        
    def is_node_light( self, node_id ):
        res = False
        node = self.get_node( node_id )
        if node:
            res = node.is_light
            self.release_nodes()
        return res
        
    def is_node_dead( self, node_id ):
        res = False
        node = self.get_node( node_id )
        if node:
            res = node.is_dead
            self.release_nodes()
        return res
    
    
    def is_node_battery_operated( self, node_id ):
        res = False
        node = self.get_node( node_id )
        if node:
            res = node.is_battery_operated
            self.release_nodes()
        return res
