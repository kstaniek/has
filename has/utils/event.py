# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
This is a implementation of Watcher, Wait and Event classes required for multithred synchronization

"""

from threading import Lock, Condition
import logging
logger = logging.getLogger('manager')


class Watcher:
    def __init__(self, callback, context):
        """
        Params:
            callback - function to be called
            context - Event object
        """
        self.callback = callback
        self.context = context
        
    def __eq__(self, other):
        if not isinstance(other, Watcher):
            return False
        if self.callback == other.callback and self.context == other.context:
            return True
        else:
            return False
            
    def __ne__(self, other):
        return not self.__eq__(other)
        
    def __call__(self):
        """
        Watcher object is callable
        """
        return self.callback( self.context )
                

def wait_multiple_callback(context):
    context.set()
    

class Wait(object):
    """
    This is abstract class that provides multiple and single wait methods for Event objects
    """
    def __init__(self):
        self.lock = Lock()
        self.watchers = []
    
    def add_watcher(self, callback, context):
        """
        Add watcher object
        
        Params:
            callback    :    callable function
            context        :    Event object
        """
        if not callable(callback):
            raise TypeError("Callback function must be callable")
            return
                
        new_watcher = Watcher( callback, context)
        with self.lock:
            self.watchers.append(new_watcher)
        
        if self.is_set():  # called from Event
            logger.debug("Wait.add_watcher: watcher signalled during creation. Making callback immediately")
            callback( context )
        
    def is_set(self):
        """
        Abstract method. Must be impleemented in child class
        """
        raise TypeError("Abstract method called. Must be implemented in Event")
            
    def remove_watcher(self, callback, context):
        """
        Remove watcher object from list
        """
        new_watcher = Watcher( callback, context )
        with self.lock:
            for watcher in self.watchers[:]:   # iterate through copy of the list
                if watcher == new_watcher:
                    self.watchers.remove(watcher)
                    return
        
    def notify(self):
        """
        Notify watchers
        """
        with self.lock:
            for watcher in self.watchers:
                watcher()    # Watcher is callable
        
    @staticmethod
    def multiple( objects, num_objects=None, timeout = None):
        """"
        Wait for one of the multiple Events passed in a objects dictionary
        
        Params:
             objects        :    dictionary of objects derived from Event clas
             mum_objects    :    number of objects in dictionary
             timeout        :    timeout - None means forewer
             
        """
        if num_objects == None:
            num_objects = len(objects)
        
        wait_event = Event("Watcher")
        
        for i in range( num_objects ):
            objects[i].add_watcher( wait_multiple_callback, wait_event)
        
        res = -1
        sig = "Signaled: "
        if ( wait_event.wait( timeout ) ):
            for i in range( num_objects ):
                if objects[i].is_set():
                    sig = sig + "[%d]" % i
                    if res == -1: #catch first event only (lower has higier priority)
                        res = i
        
        logger.debug("Wait.multiple: %s" % sig )
        
        for i in range( num_objects ):
            objects[i].remove_watcher( wait_multiple_callback, wait_event )
        
        wait_event.clear()
        return res
        
    @staticmethod
    def single( single_object, timeout = None):
        """
        Wait for single Event emulated with Wait.multiple
        """
        objects = [single_object]
        return Wait.multiple(objects, 1 , timeout)

class Event(Wait):
    def __init__(self, name):
        self.__flag = False
        self.__name = name
        self.__cond = Condition(Lock())
        Wait.__init__(self)    
    
    def __repr__(self):
        return self.__name
            
    def is_set(self):
        return self.__flag

    def set(self):
        self.__cond.acquire()
        try:
            self.__flag = True
            self.__cond.notify_all()
        finally:
            self.__cond.release()
        
        self.notify()
        
    def clear(self):
        self.__cond.acquire()
        try:
            self.__flag = False
        finally:
            self.__cond.release()
        
    def wait(self, timeout=None):
        self.__cond.acquire()
        try:
            signaled = self.__flag
            if not signaled:
                signaled = self.__cond.wait(timeout)
            return signaled
        finally:
            self.__cond.release()    
        