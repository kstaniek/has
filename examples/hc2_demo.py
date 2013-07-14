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

from tkinter import *
from tkinter import ttk
from tkinter import messagebox

from queue import Queue, Empty

import threading




class NodeInfo:
    """
    This is a class containing mimimal information required to store the information about the nodes    
    """
    def __init__(self):
        self.network_id = None
        self.node_id = None
        self.value_ids = []    

nodes = []

initFailed = True
criticalSection = Lock()    
    
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
        if notification_type == Notification.Type_DriverReady:
            context.on_message("StatusUpdate","Driver Ready")
            initFailed = False
            
        elif notification_type == Notification.Type_DriverFailed:
            context.on_message("StatusUpdate","Driver Failed")
        
        elif notification_type == Notification.Type_DriverReset:
            context.on_message("StatusUpdate","Driver Reset")
            
        elif notification_type == Notification.Type_AllNodesQueried:
            context.on_message("StatusUpdate","All Nodes Queried")
                
        elif notification_type == Notification.Type_NodeAdded:
            node_info = NodeInfo()
            node_info.network_id = notification.network_id
            node_info.node_id = notification.node_id
            nodes.append(node_info)
            context.on_message('NodeAdded', notification)
            
            
        elif notification_type == Notification.Type_NodeRemoved:
            network_id = notification.network_id
            node_id = notification.node_id
            
            for node in nodes[:]:
                if node_id == node.node_id and network_id == node.network_id:
                    nodes.remove(node)
                    del node
                    context.on_message('NodeRemoved', notification)
                    break
        
        elif notification_type == Notification.Type_NodeChanged:
            context.on_message('NodeChanged', notification)
        
        elif notification_type == Notification.Type_ValueAdded:
            #print("Manager: Value Added %s" % (notification.node_id ) )
            node_info = get_node_info( notification )
            if node_info is not None:
                node_info.value_ids.append( notification.value_id )    
                context.on_message('ValueAdded', notification)
        
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
            text = "{0} Node {1}: {2} @ {3} changed {4} to {5}".format( str(datetime.today()), node_id, node_name, node_location_name, value_type, value )
            context.on_message('ValueChanged', notification)
            context.on_message("StatusUpdate", text)
                        
            
        elif notification_type == Notification.Type_NodeQueriesComplete:
            node_name = Manager.get_node_name( notification.network_id, notification.node_id )
            context.on_message('NodeQueriesComplete', notification)
            

class HASApp():
    def __init__(self, root):
        self.queue = Queue()
        self.root = root
        #self.root.protocol("WM_DELETE_WINDOW", self.callback)
        self.tree = ttk.Treeview() #columns=('Node ID', 'type', 'size'), displaycolumns='size')
        
        self.tree.tag_configure('updated', foreground='red')
        self.tree.tag_configure('normal', foreground='black')
        self.tree.pack(side=TOP, fill=BOTH, expand=Y)
        
        
        self.status = StringVar()
        Label(root, textvariable=self.status).pack()
        
        
        
        root.bind('<<open-config-dialog>>', self.config_dialog)
        root.createcommand('::tk::mac::ShowPreferences', self.config_dialog)
        root.bind('<<close-all-windows>>', self.callback)
        root.createcommand('exit', self.callback)
        
    
    def status_update(self, notification):
        self.status.set(str(notification))
    
    
    def callback(self):
        if messagebox.askokcancel("Quit", "Do you really wish to quit?"):
            self.running = 0
        #self.root.quit()
        
    
    def run(self):
        self.running = 1
        Manager.add_watcher( OnNotification, self)
        Manager.read_config("manager.ini")
        
        #self.thread1 = threading.Thread(target=self.worker_thread)
        #self.thread1.start()
        self.queue_check()
        
        
    def config_dialog(event=None):
        if messagebox.askokcancel("Quit", "Do you really wish to quit?"):
            print("config")
        
        
    def add_node(self, notification):
        item_id = "{0}:{1}".format(notification.network_id, notification.node_id)
        
        if not self.tree.exists(item_id):
            text = "Node {0}:".format(notification.node_id)
            self.tree.insert("", "end", item_id, text=text)
    
    def node_queries_complete(self, notification):
        
        item_id = "{0}:{1}".format(notification.network_id, notification.node_id)
        node_name = Manager.get_node_name( notification.network_id, notification.node_id )
        node_location_name = Manager.get_node_location_name( notification.network_id, notification.node_id )
        node_type = Manager.get_node_type( notification.network_id, notification.node_id )
        #print(node_location_name)
        if not self.tree.exists(node_location_name):
            self.tree.insert("", "end", node_location_name, text=node_location_name)
            
        text = "{1} (Node:{0}:{2})".format(notification.node_id, node_name, node_type)
        self.tree.item(item_id, text=text)
        self.tree.move(item_id, node_location_name, "end")
            
    def remove_node(self, notification):
        item_id = "{0}:{1}".format(notification.network_id, notification.node_id)
        if self.tree.exists(item_id):
            self.tree.delete(item_id)
        
    def update_node(self, notification):
        item_id = "{0}:{1}".format(notification.network_id, notification.node_id)
        self.tree.item(item_id, tags=('updated')) 
        self.root.after(10000, self.reset_foreground, item_id)       
        
    def add_value(self, notification):
        item_id = "{0}:{1}".format(notification.network_id, notification.node_id)
        obj_value_id = notification.value_id
        value_type = Manager.get_value_type( obj_value_id )
        value =  Manager.get_value_as_string( obj_value_id )
        last_changed = Manager.get_value_last_changed(obj_value_id)
        text="{0}={1} ({2})".format(value_type,value,last_changed)
        self.tree.insert(item_id,"end", obj_value_id.id, text=text)
        
    def change_value(self, notification):
        obj_value_id = notification.value_id
        if self.tree.exists(obj_value_id.id):
            value_type = Manager.get_value_type( obj_value_id )
            value =  Manager.get_value_as_string( obj_value_id )
            last_changed = Manager.get_value_last_changed(obj_value_id)
            text="{0}={1} ({2})".format(value_type,value,last_changed)
            self.tree.item(obj_value_id.id, text=text, tags=('updated'))
        
        self.root.after(10000, self.reset_foreground, obj_value_id.id)    
        
        
    def reset_foreground(self, item):
        self.tree.item(item, tags=('normal'))
        
        
    def on_message(self, message, notification):
        self.queue.put_nowait((message,notification))
        
    def queue_check(self):
        while self.queue.qsize():
            try:
                message, notification = self.queue.get_nowait()
                if message == 'NodeAdded':
                    self.add_node(notification)
                elif message == 'ValueAdded':
                    self.add_value(notification)
                elif message == 'ValueChanged':    
                    self.change_value(notification)
                elif message == 'NodeRemoved':
                    self.remove_node(notification)
                elif message == 'NodeChanged':
                    self.update_node(notification)
                elif message == 'NodeQueriesComplete':
                    self.node_queries_complete(notification)
                elif message == 'StatusUpdate':
                    self.status_update(notification)
            except Empty:
                pass
                
        if not self.running:
            Manager.close()
            print("Done")
            self.root.destroy()
            
        else:
            self.root.after(1000, self.queue_check)

def main():    
    root = Tk(className="Home Automation System")
    title=root.title("Home Automation System")
    width=root.winfo_screenwidth()
    height=root.winfo_screenheight()
    root.geometry("{0}x{1}".format( width,height ) )
    app = HASApp(root)
    app.run()
    root.mainloop()

        
if __name__ == "__main__":
    main()
    exit()
    



