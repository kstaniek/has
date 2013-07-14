# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
HC2 Controller implementaiton

"""

from has.utils.event import Event
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError
import http.cookiejar

from http.client import HTTPConnection, BadStatusLine, ResponseNotReady, CannotSendRequest, HTTPException
from base64 import b64encode
import string
import socket
from queue import PriorityQueue, Queue, Empty
from threading import Thread
import re
from random import random

import logging
from socket import timeout, gaierror, gethostbyname, herror, _GLOBAL_DEFAULT_TIMEOUT
from time import time

from has.utils.event import Wait

import logging
logger = logging.getLogger('manager')


class ResponseHandler(urllib.request.BaseHandler):
    def __init__(self, parent_class):
        self.__parent_class = parent_class
        self.__handlers = dict (  api_refreshStates = self.__handle_api_refreshStates,
                                api_loginStatus = self.__handle_api_loginStatus,
                                default = self.__handle_default,
                                proxy = self.__handle_proxy)
        super().__init__()
    
    def http_response(self, request, response):
        return self._response(request, response)
    
    def https_response(self, request, response):
        return self._response(request, response)
    
    def _response(self, request, response):
        command, parameters = self.__decode_command(request)
        logger.debug("ResponseHandler: COMMAND {0}, PARAMS: {1}".format(command, parameters))
        
        #print("contoller: handle response")
        #print("----request------")
        #print(request.full_url)
        #print(request.type)
        #print(request.selector)
        #print(request.data)
        #print(request.method)
        #print('---response-------')
        #print(response.info())
        #print("Response msg:%s" % response.msg)
        #print(response.status)
        #print("COMMAND: %s, PARAMS: %s" % (command, parameters))
        #print('---done-------')
        
        if response.status == 200:
            if command in self.__handlers:
                return self.__handlers[command](command, parameters, response)
            else:
                return self.__handle_command(command, parameters, response)
            
        return response
        
    def __response_read(self, response):
        return response.read().decode('UTF-8')
    
    def __decode_command(self, request):
        command = "default"
        parameters = {}
        selector = urllib.parse.unquote(request.selector)
        match = re.search("/(api/[a-z|A-Z|/]*)\?*(.*)", selector)
        if match:
            command = match.group(1).replace('/','_')
            qs = match.group(2)
            parameters = urllib.parse.parse_qs(qs)
            #print("PARAMS: %s" % parameters)
            
        elif request.selector == "/fibaro/index.php":
            command = 'proxy' 
        
        return command, parameters
    
    def __handle_proxy(self, command, parameters, response):
        result = self.__response_read(response)
        match = re.search("newProxyLite(.*)&req", result)
        if match:
            self.__parent_class.proxy = "/newProxyLite" + match.group(1) + "&req="
        else:
            self.__parent_class.proxy = ""
        return response
        
    def __handle_api_loginStatus(self, command, parameters, response):
        result = self.__response_read(response)
        match = re.search('"status":(false|true)', result)
        if match:
            #print("LOGIN STATUS: %s" % match.group(1))
            if match.group(1) == 'true':
                self.__parent_class.connected_event.set()
                self.__parent_class.connected = True
            else:
                self.__parent_class.tx_put('GET','/api/home')
                self.__parent_class.tx_put('GET','/api/loginStatus')
                
        return response
            
    def __handle_api_refreshStates(self, command, parameters, response):
        result = self.__response_read(response)
        match = re.search('"last":([0-9]*)', result)
        if match:
            self.__parent_class.last_refresh = match.group(1)
            #print("LAST_REFRESH:%s" % self.parent_class.last_refresh)
        self.__parent_class.rx_put( command, parameters, result )
        self.__parent_class.tx_put('GET','/api/refreshStates')
        return response
    
    def __handle_command(self, command, parameters, response):
        #print("HANDLE COMMAND:%s" % command)
        result = self.__response_read(response)
        self.__parent_class.rx_put( command, parameters, result )
        return response
    
    def __handle_default(self, command, parameters, response):
        #print("HANDLE DEFAULT:%s" % command)
        return response
    
            

class HC2HTTPBasicAuthHandler(urllib.request.HTTPBasicAuthHandler):
    """
    Extension to http_error_401 setting the auth_required flag to True
    when authentication required.
    It can add the authentication header to the requests avoiding request to be resend with auth header.
    """
    def __init__(self, parent_class):
        """
        Saving the parnet class reference
        path
        """
        self.__parent_class = parent_class
        super().__init__()

    def http_error_401(self, req, fp, code, msg, headers):
        """
        Passing request to the super class and setting the flag:
        """
        response = super().http_error_401(req, fp, code, msg, headers)
        self.__parent_class.auth_required = True
        return response
        

    
class HC2Controller(Event, Thread):
    def __init__(self, host, username, password, port=80, remote=False, remote_server=None, remote_username=None, remote_password=None):
        Event.__init__(self, "Controller")
        Thread.__init__(self)
        self.proxy = None
        self.remote = remote
        self.host = host
        self.remote_server  = remote_server
        self.remote_username = remote_username
        self.remote_password = remote_password
        
        self.auth = b64encode(("%s:%s" % (username, password)).encode('ascii')).decode('ascii')
        self.auth_required = False
        
        self.__rx_queue = Queue()
        self.__tx_queue = Queue()
        
        self.last_refresh = None
        self.__running = False
        
        self.connected_event = Event("Connected")
        self.connected = False

        cj = http.cookiejar.CookieJar()
        cookie_handler = urllib.request.HTTPCookieProcessor(cj)
        password_handler = HC2HTTPBasicAuthHandler(self)
        if self.remote:
            url = "https://" + self.remote_server  + "/newProxyLite"
        else:
            url = "http://" + self.host 
        
        password_handler.add_password("fibaro", url, username, password)
        response_handler = ResponseHandler(self)
        self._opener = urllib.request.build_opener( password_handler, cookie_handler, response_handler)
        
    
    def open(self, network):
        " Request default page"
        self.tx_put('GET','')
        
        if self.remote:
            
            """
            Fill in the parameters for login web form
            and send http POST
            """
            
            params = {}
            params['login'] = self.remote_username
            params['pwd'] = self.remote_password
            """
            to handle fibaro bug in login form
            """
            if 'dom' in self.remote_server:
                params['loguj'] = 'Loguj'
            elif 'home' in self.remote_server:
                params['loguj_ra'] = 'Loguj'
                
            self.tx_put('POST','/cmh/index.php?page=login', params)
            #self.tx_put('/cmh/index.php')
            self.tx_put('GET','/cmh/index.php?page=choose_ui&hc={0}'.format(network))
            self.tx_put('GET','/fibaro/index.php')
            
        #self.tx_put('/api/interface/data')
        #self.tx_put('/fibaro/pl/home/index.php')
        
        self.tx_put('GET','/api/loginStatus')
        #self.tx_put('/api/globalVariables')
        #self.tx_put('/api/globalVariables')
            
        self.start()

        
        res = Wait.single(self.connected_event, 10)
        
        if res == -1:
            """
            Timeout
            """
            return False
        else:
            self.tx_put('GET','/api/settings/info')
            return True

        
    def run(self):
        """
        Main controller loop
        """
        logger.debug("HC2Controller.run: entering controller main loop")
        self.__running = True
        while self.__running:
            method, command, parameters = self.__tx_queue.get()
            if command == 'exit':
                self.__tx_queue.task_done()
                break
            else:  # develop retry loop in case sending failure / exception
                if not self.send(method, command, parameters):
                    self.rx_put('error')
                    
                self.__tx_queue.task_done()
        logger.debug("HC2Controller.run: exiting controller main loop")

        
    
    def close(self):
        """
        Closing the contoller by sending 'exit' command
        """
        logger.debug("HC2Controller.close: closing the controller")
        self.__running = False
        self.connected = False
        self.tx_put(None, 'exit')
        self.join()
        
    
    def tx_put(self, method, url, parameters = None):
        """
        Put url request with paramenters to the transmit queue
        
        Params:
            url:    string containing url to be sent to HC2
            params: dictionary containing parameters
        """
        self.__tx_queue.put_nowait( (method, url, parameters) )
        
        
    def rx_put(self, command, parameters=None, response=None):
        """
        Put the command and response back to receive queue
        
        Params:
            message:    tuple of (command, content)
            where command is a string in format /api/<command> and
            content is response of this command returned by HC2
        """
        #print(command, parameters, response)
        self.__rx_queue.put_nowait( (command, parameters, response) )
        self.set()
        
        
    def receive(self):
        """
        Returns the message which is a tuple of (command, parameters, response)
        and clear the controller Event when rx queue is empty
        """
        try:
            message = self.__rx_queue.get()
            if self.__rx_queue.empty():
                self.clear()
            return message

        except Empty:
            self.clear()
            return None

    def send(self, method, api, parameters = None):
        """
        Send the HTTP Request to HC2.
        It handles both local and remote access
        
        Params:
            api:        API command to send i.e. /api/deivice
            paramerers: Dictionary with parameters. If not none the POST instead of GET is used.
        """
        if self.remote:
            if self.proxy:
                api = urllib.parse.quote(api)
                url = "https://" + self.remote_server  + self.proxy + api
            else:
                url = "https://" + self.remote_server  + api
        else:
            url = "http://" + self.host + api
    
        if api == '/api/refreshStates':
            rand=random()
            if self.last_refresh != None:
                params = "?last=" + str(self.last_refresh) + '&rand='+str(rand) + '&lang=en'
                if self.remote:
                    params = urllib.parse.quote(params)
            else:
                params = ""
            url = url + params
        
        
        if method == 'POST' and parameters is not None:
            parameters = urllib.parse.urlencode(parameters).encode('utf-8')
        if method == 'PUT' and parameters is not None:
            parameters = parameters.encode('utf-8')    
        
        logger.debug("REQUEST: {0} {1} {2}".format(method, url, parameters) )
        
        request = urllib.request.Request(url, data=parameters, method=method)
                
        if self.auth_required:
            request.add_header("Authorization","Basic %s" % self.auth)
        
        try:    
            #response = self._opener.open(request, parameters, timeout=60).read()
            response = self._opener.open(request, timeout=60).read()
        except URLError as e:
            logger.error("HC2Controller.send: URLError exception reason: {0}".format(e.reason))
        except HTTPError as e:
            logger.error("HC2Controller.send: HTTPError exception reason: {0} code: {1}".format(e.reason, e.code))
        except TimeoutError as e:
            logger.error("HC2Controller.send: TimeoutError exception reason: {0}".format(e) )            
        except timeout as e:
            logger.error("HC2Controller.send: Timeout")
        except gaierror as e:
            logger.error("HC2Controller.send: Get Address Info Error exception")
        except herror as e:
            logger.error("HC2Controller.send: Get Host Error exception")
        else:
            return True
        
        logger.debug("REQUEST: {0} {1} {2}".format(method, url, parameters) )
        logger.error("HC2Controller.send: Request has not been sent")
        return False
                