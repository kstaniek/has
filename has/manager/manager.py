# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
Manager class implementation

"""


from has.utils.event import Watcher
from has.utils.notification import Notification
from has.manager.hc2.hc2driver import HC2Driver

import logging
import time
from configparser import ConfigParser
from threading import Lock


#logging.basicConfig(format='%(asctime)s %(levelname)s:\t%(message)s', filename='manager.log', filemode='w', level=logging.DEBUG)
#logging.basicConfig(format='%(asctime)s %(levelname)s:\t%(message)s', level=logging.DEBUG)
#logging.basicConfig(format='%(asctime)s %(levelname)s:\t%(message)s', level=logging.INFO)
logger = logging.getLogger('manager')


def singleton(cls):
    return cls()

@singleton    
class Manager(object):
    """Manager object to run the entire application"""
    def __init__( self ):
        self.pending_drivers = []
        self.ready_drivers = []
        self.watchers = []
        self.notification_lock = Lock()
        
    def read_config(self, filename='manager.ini'):
        config = ConfigParser()
        config.read(filename)
        print(config.sections())
        
        
        
        for section in config.sections():
            if section.startswith('driver'):
                driver_cls = section.split('.')[1]
                params = config._sections[section]
                params['remote'] = config[section].getboolean('remote')
                driver = None
                try:
                    driver = eval("{0}(**params)".format(driver_cls))
                    print(driver)
                    if not self.add_driver(driver):
                        logger.error( "Driver for network {0} not added".format ( params['network'] ) )
                except NameError as e:
                    logger.error( "Driver class '{0}' not implemented but configured".format ( driver_cls ) )
                except TypeError as e:
                    logger.error( "Missing configuration parameter '{0}'".format( e.args[0] ) )
            
    def close(self):
        self.remove_driver()
    
    def add_driver(self, new_driver):
        new_network_id = new_driver.get_network()
        for driver in self.pending_drivers:
            if driver.get_network() == new_network_id:
                logger.error( "Cannot add driver for %s - driver already exists" % new_network_id )
                return False
                
        for driver in self.ready_drivers:
            if driver.get_network() == new_network_id:
                logger.error( "Cannot add driver for %s - driver already exists" % new_network_id )
                return False
                
        self.pending_drivers.append(new_driver)
        new_driver.set_manager(self)
        new_driver.start()
        return True
        
    def remove_driver(self, network_id=None):
        remove_all = True if network_id == None else False
        print("Remove all: %s" % remove_all)
        
        logger.debug( "Manager.remove_driver: %s" % network_id )
        for driver in self.pending_drivers[:]:
            if (driver.get_network() == network_id) or remove_all:
                self.pending_drivers.remove(driver)
                driver.stop()
                logger.info( "Driver %s - removed" % driver.get_network() )
                
        
        for driver in self.ready_drivers[:]:
            if (driver.get_network() == network_id) or remove_all:
                self.ready_drivers.remove(driver)
                driver.stop()
                logger.info( "Driver %s - removed" % driver.get_network() )
                    
    def get_driver(self, network_id):
        for driver in self.ready_drivers:
            if driver.get_network() == network_id:
                return driver
        return None    
    
    
    def set_driver_ready(self, driver, success):
        found = False
        for driver_obj in self.pending_drivers:
            if driver_obj.get_network() == driver.get_network():
                print('found: %s' % driver)
                self.pending_drivers.remove(driver)
                found = True
                break
        if found:
            if success:
                logger.info( "Driver for %s is now ready" % driver.get_network() )
                notification = Notification( Notification.Type_DriverReady )
                self.ready_drivers.append( driver )
            else:
                notification = Notification( Notification.Type_DriverFailed )
                driver.stop()
            
            
            notification.network = driver.get_network()
            driver.queue_notification( notification ) 
    
    
    def add_watcher(self, callback, context):
        watcher = Watcher( callback, context )
        with self.notification_lock:
            for w in self.watchers[:]:
                if w == watcher: # Watcher already exists
                    self.notification_lock.release()
                    return False
            self.watchers.append( watcher )
        return True
        
    def remove_watcher(self, callback, context):
        watcher = Watcher( callback, context )
        with self.notification_lock:
            for w in self.watchers[:]:
                if w == watcher:
                    self.watchers.remove( watcher )
                    return True
        return False    
        
    def notify_watchers(self, notification):
        with self.notification_lock:
            for watcher in self.watchers:
                watcher.callback( notification, watcher.context)

#-------------------- nodes
    
    
    def get_node_type(self, network_id, node_id ):
        driver = self.get_driver( network_id )
        if driver:
            return driver.get_node_type( node_id )
        return "Unknown"
        
    def get_node_name(self, network_id, node_id ):
        driver = self.get_driver( network_id )
        if driver:
            return driver.get_node_name( node_id )
        return "N/A"
    
    def get_node_description( self, network_id, node_id ):
        driver = self.get_driver( network_id )
        if driver:
            return driver.get_node_description( node_id )
        return ""
            
    def get_node_location_name(self, network_id, node_id ):
        driver = self.get_driver( network_id )
        if driver:
            return driver.get_node_location_name( node_id )    
        return "Unknown"    
    
    def is_node_light(self, network_id, node_id):
        res = False
        driver = self.get_driver( network_id )
        if driver:
            res = driver.is_node_light( node_id )
        return res
        
    def is_node_dead(self, network_id, node_id):
        res = False
        driver = self.get_driver( network_id )
        if driver:
            res = driver.is_node_dead( node_id )
        return res
    
    def is_node_battery_operated(self, network_id, node_id):
        res = False
        driver = self.get_driver( network_id )
        if driver:
            res = driver.is_node_battery_operated( node_id )
        return res
        
#---------------------- values

    def get_value(self, value_id):
        v = None
        driver = self.get_driver( value_id.network_id )
        driver.lock_nodes()
        value_obj = driver.get_value( value_id )
        if value_obj is not None:
            v = value_obj.get()
        driver.release_nodes()
        return v
        
    def get_value_as_string(self, value_id):
        v = None
        driver = self.get_driver( value_id.network_id )
        driver.lock_nodes()
        value_obj = driver.get_value( value_id )
        if value_obj is not None:
            v = value_obj.get_as_string()
        driver.release_nodes()
        return v
    
    def set_value(self, value_id, value):
        try:
            driver = self.get_driver( value_id.network_id)
            driver.lock_nodes()
            value_obj = driver.get_value( value_id )
            if value_obj is not None:
                v = value_obj.set( value )
            driver.release_nodes()
        
        except Exception as e:
            print(e)
        return
    
    def get_value_id(self, value_id):
        unique_value_id = None
        driver = self.get_driver( value_id.network_id )
        driver.lock_nodes()
        value = driver.get_value( value_id )
        if value is not None:
            unique_value_id = value.value_id
        driver.release_nodes()
        
        return unique_value_id
    
    
    def get_value_type(self, value_id):
        value_type = None
        driver = self.get_driver( value_id.network_id )
        driver.lock_nodes()
        value = driver.get_value( value_id )
        if value is not None:
            value_type = value.value_type
        driver.release_nodes()
        return value_type
        
    def get_value_last_changed(self, value_id):
        value_last_changed = None
        driver = self.get_driver( value_id.network_id )
        driver.lock_nodes()
        value = driver.get_value( value_id )
        if value is not None:
            value_last_changed = value.last_changed.strftime("%Y-%m-%d %H:%M:%S")
        driver.release_nodes()
        return value_last_changed
    
    def get_value_units(self, value_id):
        units = None
        driver = self.get_driver( value_id.network_id)
        driver.lock_nodes()
        value = driver.get_value( value_id )
        if value is not None:
            units = value.units
        driver.release_nodes()
        return units
