# Copyright (c) Klaudisz Staniek.
# See LICENSE for details.

"""
General purpose Notification class

"""


class Notification:
	Type_DriverReady, \
	Type_DriverFailed, \
	Type_DriverReset, \
	Type_NodeAdded, \
	Type_NodeRemoved, \
    Type_NodeChanged, \
	Type_ValueAdded, \
	Type_ValueRemoved, \
	Type_ValueChanged, \
	Type_NodeQueriesComplete, \
	Type_AllNodesQueried = range(11)
	
	def __init__(self, notification_type):
		self.__notification_type = notification_type
		self.__node_id = None
		self.__network_id = None
		self.__device_rype = None
		self.__value_id = None
	
	@property	
	def type(self):
		return self.__notification_type
		
	@property
	def node_id(self):
		""" Unique Node ID """
		return self.__node_id
	
	@node_id.setter
	def node_id(self, value):
		self.__node_id = value
	
	@property
	def node_type(self):
		return self.__node_type
	
	@node_type.setter
	def node_type(self, value):
		self.__node_type = value
	
	@property
	def network_id(self):
		return self.__network_id
	
	@network_id.setter
	def network_id(self, value):
		self.__network_id = value
	
	@property
	def value_id(self):
		return self.__value_id
	
	@value_id.setter
	def value_id(self, value):
		self.__value_id = value
	