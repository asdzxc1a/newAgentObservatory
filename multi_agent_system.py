#!/usr/bin/env python3
"""
Multi-Agent System Coordinator
Orchestrates multiple AI agents working on different tasks with real-time coordination
"""

import asyncio
import json
import logging
import subprocess
import time
import uuid
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import threading
import queue
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgentStatus(Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    COMPLETED = "completed"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Task:
    id: str
    title: str
    description: str
    priority: TaskPriority
    assigned_agent: Optional[str] = None
    status: str = "pending"
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    dependencies: List[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class Agent:
    id: str
    name: str
    role: str
    capabilities: List[str]
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    project_path: str = "."
    session_id: Optional[str] = None
    process: Optional[subprocess.Popen] = None
    last_activity: float = None
    
    def __post_init__(self):
        if self.last_activity is None:
            self.last_activity = time.time()

@dataclass
class AgentMessage:
    id: str
    from_agent: str
    to_agent: str
    message_type: str
    content: str
    timestamp: float
    task_id: Optional[str] = None

class MultiAgentCoordinator:
    def __init__(self, observability_server: str = "http://localhost:4000"):
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.messages: List[AgentMessage] = []
        self.task_queue = queue.PriorityQueue()
        self.message_queue = queue.Queue()
        self.observability_server = observability_server
        self.running = False
        self.coordination_thread = None
        
    def register_agent(self, agent: Agent) -> bool:
        """Register a new agent with the coordinator"""
        try:
            self.agents[agent.id] = agent
            logger.info(f"Registered agent: {agent.name} ({agent.role})")
            self._notify_observability("agent_registered", {
                "agent_id": agent.id,
                "agent_name": agent.name,
                "role": agent.role,
                "capabilities": agent.capabilities
            })
            return True
        except Exception as e:
            logger.error(f"Failed to register agent {agent.id}: {e}")
            return False
    
    def create_task(self, title: str, description: str, priority: TaskPriority, 
                   dependencies: List[str] = None) -> str:
        """Create a new task and add it to the queue"""
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            title=title,
            description=description,
            priority=priority,
            dependencies=dependencies or []
        )
        
        self.tasks[task_id] = task
        # Priority queue uses negative priority for max-heap behavior
        self.task_queue.put((-priority.value, time.time(), task_id))
        
        logger.info(f"Created task: {title} (Priority: {priority.name})")
        task_dict = asdict(task)
        task_dict['priority'] = task.priority.value  # Convert enum to int
        self._notify_observability("task_created", task_dict)
        
        return task_id
    
    def _notify_observability(self, event_type: str, data: Dict[str, Any]):
        """Send events to the observability server"""
        try:
            event_data = {
                "source_app": "multi-agent-coordinator",
                "session_id": "coordinator",
                "hook_event_type": event_type,
                "payload": data,
                "timestamp": int(time.time() * 1000)
            }
            
            response = requests.post(
                f"{self.observability_server}/events",
                json=event_data,
                timeout=5
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to send event to observability server: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Could not send event to observability server: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            "agents": {aid: asdict(agent) for aid, agent in self.agents.items()},
            "tasks": {tid: asdict(task) for tid, task in self.tasks.items()},
            "queue_size": self.task_queue.qsize(),
            "message_count": len(self.messages),
            "running": self.running
        }