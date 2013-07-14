#!/usr/bin/env python3

# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
This is an example application demonstrating the event driven driver capabilities and API usage
"""


from has.manager.manager import Manager
from has.utils.notification import Notification
from threading import Lock, RLock, Condition
from datetime import datetime
import configparser

class NodeInfo:
    """
    This is a class containing mimimal information required to store the information about nodes    
    """
    def __init__(self):
        self.network_id = None
        self.node_id = None
        self.value_ids = []    

nodes = []


initFailed = True

criticalSection = Lock()    
initLock = RLock()
initCondition = Condition(initLock)    

    
def get_value_obj(value_id):
    for node in nodes:
        for value in node.value_ids:
            if value.id == value_id:
                return value
                
def get_node_info( notification ):
    network_id = notification.network_id
    node_id = notification.node_id
    
    for node in nodes:
        if node.network_id == network_id and node.node_id == node_id:
            return node
    return None

def OnNotification( notification, context ):
    global initFailed
    global criticalSection
    global initCondition
    
    with criticalSection:
        notification_type = notification.type
        #print "OnNotification: %d" % type
        if notification_type == Notification.Type_DriverReady:
            print("Manager: Driver Ready!")
            initFailed = False
            
        elif notification_type == Notification.Type_DriverFailed:
            print("Manager: Driver Failed!")
            with initCondition:
                initFailed = True
                initCondition.notifyAll()
        
        elif notification_type == Notification.Type_DriverReset:
            print("Manager: Driver Reset!")
        
        elif notification_type == Notification.Type_AllNodesQueried:
            print("Manager: All Nodes Queried")
            with initCondition:
                initCondition.notifyAll()
                
        elif notification_type == Notification.Type_NodeAdded:
            print("Manager: Node Added %s" % (notification.node_id ) )
            
            node_info = NodeInfo()
            node_info.network_id = notification.network_id
            node_info.node_id = notification.node_id
            nodes.append(node_info)
            
        elif notification_type == Notification.Type_NodeRemoved:
            print( "Manager: Node Removed %s" % (notification.node_id ) )
            network_id = notification.network_id
            node_id = notification.node_id
            
            for node in nodes[:]:
                if node_id == node.node_id and network_id == node.network_id:
                    nodes.remove(node)
                    del node
                    break
        
        elif notification_type == Notification.Type_ValueAdded:
            print("Manager: Value Added %s" % (notification.node_id ) )
            node_info = get_node_info( notification )
            if node_info is not None:
                node_info.value_ids.append( notification.value_id )    
        
        elif notification_type == Notification.Type_ValueChanged:
            node_info = get_node_info( notification )
            
            network_id = node_info.network_id
            node_id = node_info.node_id
            value_id = notification.value_id
            
            value_type = Manager.get_value_type( value_id )
            value_id = Manager.get_value_id( value_id )
            value =  Manager.get_value_as_string( value_id )
            units = Manager.get_value_units( value_id )
            node_name = Manager.get_node_name( network_id, node_id )
            node_location_name = Manager.get_node_location_name( network_id, node_id )
            print("%s" % str(datetime.now()), end="" )
            print(" Node %03s: %s in %s changed %s to %s" % ( node_id, node_name, node_location_name, value_type, value ))
            
        elif notification_type == Notification.Type_NodeQueriesComplete:
            pass
            print("Manager: NodeQueriesComplete %s" % (notification.node_id ))
            


        
if __name__ == "__main__":
    
    initCondition.acquire()
    
    Manager.add_watcher( OnNotification, None)
    Manager.read_config("manager.ini")
    
    print("Condition wait")
    initCondition.wait(60)
    print("Condition relese")
    print("Pending drivers %s:" % Manager.pending_drivers)
    print("Ready drivers %s:" % Manager.ready_drivers)
    initCondition.release()
    if not initFailed:
    
        print("------------------------------------------------------------")
        for node in nodes:
            is_light = Manager.is_node_light(node.network_id, node.node_id)
            is_dead = Manager.is_node_dead(node.network_id, node.node_id)
            node_type = Manager.get_node_type(node.network_id, node.node_id)
            name = Manager.get_node_name(node.network_id, node.node_id)
            room = Manager.get_node_location_name(node.network_id, node.node_id)
            desc = Manager.get_node_description(node.network_id, node.node_id)
            if is_light or True:
                print("Node id: %s, Name: %s, Room: %s, Type: %s, Light: %s, Dead: %s, Desc: %s" % (node.node_id, name, room, node_type, is_light, is_dead, desc) )
                for valueID in node.value_ids:
                    print("ValueID:%s Type: %s, Value %s" % ( valueID.id, Manager.get_value_type( valueID ), Manager.get_value( valueID ) ))
                                
        print("------------------------------------------------------------")
        
        for node in nodes:
            is_light = Manager.is_node_light(node.network_id, node.node_id)
            is_dead = Manager.is_node_dead(node.network_id, node.node_id)
            node_type = Manager.get_node_type(node.network_id, node.node_id)
            name = Manager.get_node_name(node.network_id, node.node_id)
            room = Manager.get_node_location_name(node.network_id, node.node_id)
            desc = Manager.get_node_description(node.network_id, node.node_id)
            if desc == "window":
                print("Node id: %s, Name: %s, Room: %s, Type: %s, Light: %s, Dead: %s, Desc: %s" % (node.node_id, name, room, node_type, is_light, is_dead, desc) )
            
        print("------------------------------------------------------------")
        
        for node in nodes:
            is_light = Manager.is_node_light(node.network_id, node.node_id)
            is_dead = Manager.is_node_dead(node.network_id, node.node_id)
            node_type = Manager.get_node_type(node.network_id, node.node_id)
            name = Manager.get_node_name(node.network_id, node.node_id)
            room = Manager.get_node_location_name(node.network_id, node.node_id)
            desc = Manager.get_node_description(node.network_id, node.node_id)
            if desc == "door":
                print("Node id: %s, Name: %s, Room: %s, Type: %s, Light: %s, Dead: %s, Desc: %s" % (node.node_id, name, room, node_type, is_light, is_dead, desc) )
            
        
        choice = input("")
        
    Manager.close()

    print("Done")



