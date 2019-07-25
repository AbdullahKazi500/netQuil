import queue
import multiprocessing
import itertools
import sys

__all__ = ["QConnect", "CConnect"]

pulse_length_default = 10 * 10 ** -12 # 10 ps photon pulse length
signal_speed = 2.998 * 10 ** 5 #speed of light in km/s
fiber_length_default = 0.0

class QConnect: 
    def __init__(self, agent_one, agent_two, transit_devices=[]):
        '''
        This is the base class for a quantum connection between two agents. 

        :param Agent agent_one: first agent in connection
        :param Agent agent_two: second agent in connection
        :param Array transit_devices: array of devices qubits travel through - assumed order: agent_one -> agent_two
        '''
        agent_one_name = agent_one.name 
        agent_two_name = agent_two.name
        
        self.source_devices = {
            agent_one_name: agent_one.source_devices,
            agent_two_name: agent_two.source_devices,
        }

        self.target_devices = {
            agent_one_name: agent_one.target_devices,
            agent_two_name: agent_two.target_devices,
        }
        
        # Assumed order of transit_devices is agent_one -> agent_two (i.e. source -> target).
        self.transit_devices = {
            agent_one_name: transit_devices, 
            agent_two_name: transit_devices[::-1]
        }

        # add connection ingress and outgress qconnection to agent_one and agent_two
        agent_one.qconnections[agent_two_name] = self
        agent_two.qconnections[agent_one_name] = self
       
        self.agents = {
            agent_one_name: agent_one,
            agent_two_name: agent_two
        }

        # create queue to keep track of multiple requests. Name of queue is name of target agent.  
        self.queues = {
            agent_one_name: queue.Queue(),
            agent_two_name: queue.Queue()
        }

    def put(self, source, target, qubits, source_time):
        ''' 
        Constructs full list of devices that each qubit must travel through. Sends the qubits
        through source devices. Places qubits and a list of transit and target 
        devices on the queue. Queue is keyed on the target Agent's name.
        
        :param String source: name of agent where the qubits being sent originated
        :param String target: name of agent receiving qubits
        :param Array qubits: array of numbers corresponding to qubits the source is sending 
        :param Float source_time: time of source agent before sending qubits
        '''
        source_devices = self.source_devices[source]
        transit_devices = self.transit_devices[source]
        target_devices = self.target_devices[target]

        non_source_devices = {
            "transit": transit_devices,
            "target": target_devices,
        }

        program = self.agents[source].program
        source_delay = 0

        if not source_devices:
            source_delay += pulse_length_default
        else:
            for device in source_devices:
                source_delay += device.apply(program, qubits)

        # Scale source delay time according to number of qubits sent
        scaled_source_delay = source_delay*len(qubits) 

        self.queues[target].put((qubits, non_source_devices, scaled_source_delay, source_time))
        return scaled_source_delay

    def get(self, agent): 
        '''
        Pops qubits off of the agent's queue. Sends qubit through transit and target devices,
        simulating a quantumm network. Return an array of the qubits that have been altered as well as
        the time it took the qubit to travel through the network. 

        :param Agent agent: agent receiving the qubits 
        '''
        qubits, devices, source_delay, source_time = self.queues[agent.name].get()
        agent.qubits = list(set(qubits + agent.qubits))

        program = self.agents[agent.name].program
       
        transit_devices = devices["transit"]
        target_devices = devices["target"]

        travel_delay = 0
        #default delays
        if not transit_devices:
            travel_delay += fiber_length_default/signal_speed
        if not target_devices:
            travel_delay += 0
          
        for device in list(itertools.chain(transit_devices, target_devices)):
            travel_delay += device.apply(program, qubits)  

        scaled_delay = travel_delay*len(qubits) + source_delay
        return qubits, scaled_delay, source_time

class CConnect: 
    def __init__(self, agent_one, agent_two, length=0.0):
        '''
        This is the base class for a classical connection between two agents. 

        :param Agent agent_one: first agent in connection
        :param Agent agent_two: second agent in connection
        :param Float length: distance between first and second agent
        '''
        agent_one_name = agent_one.name
        agent_two_name = agent_two.name
        agent_one.cconnections[agent_two_name] = self
        agent_two.cconnections[agent_one_name] = self
       
        self.agents = { 
            agent_one_name: agent_one, 
            agent_two_name: agent_two
        }

        self.length = length
        '''
        Create queue to keep track of multiple requests. Name of queue is name of
        target agent.  
        '''
        self.queues = {
            agent_one_name: multiprocessing.Queue(),
            agent_two_name: multiprocessing.Queue()
        }

    def put(self, target, cbits):
        ''' 
        Places cbits on queue keyed on the target Agent's name

        :param String target: name of recipient of program
        :param Array cbits: array of numbers corresponding to cbits agent is sending
        '''
        csource_delay = pulse_length_default * 8 * sys.getsizeof(cbits)
        self.queues[target].put((cbits, csource_delay))
        return csource_delay

    def get(self, agent): 
        ''' 
        Pops cbits off of the agent's queue and adds travel delay

        :param String agent: name of the agent receiving the cbits
        '''
        cbits, source_delay = self.queues[agent].get()
        travel_delay = self.length/signal_speed
        
        scaled_delay = travel_delay*len(cbits) + source_delay

        return cbits, scaled_delay