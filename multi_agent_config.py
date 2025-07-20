#!/usr/bin/env python3
"""
Multi-Agent System Configuration
Defines agent templates, task templates, and system configuration
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from enum import Enum
import json
from pathlib import Path

class AgentType(Enum):
    FRONTEND_DEVELOPER = "frontend_developer"
    BACKEND_DEVELOPER = "backend_developer"
    DEVOPS_ENGINEER = "devops_engineer"
    QA_TESTER = "qa_tester"
    TECHNICAL_WRITER = "technical_writer"
    ARCHITECT = "architect"
    DATA_SCIENTIST = "data_scientist"
    SECURITY_SPECIALIST = "security_specialist"

@dataclass
class AgentTemplate:
    type: AgentType
    name: str
    description: str
    capabilities: List[str]
    default_tools: List[str]
    prompt_template: str
    max_concurrent_tasks: int = 1
    preferred_project_structure: List[str] = None

@dataclass
class TaskTemplate:
    category: str
    title_template: str
    description_template: str
    required_capabilities: List[str]
    estimated_duration: int  # in minutes
    complexity_score: int  # 1-10
    dependencies_template: List[str] = None

class MultiAgentConfig:
    def __init__(self, config_file: str = "multi_agent_config.json"):
        self.config_file = Path(config_file)
        self.agent_templates = self._load_agent_templates()
        self.task_templates = self._load_task_templates()
        self.system_config = self._load_system_config()
    
    def _load_agent_templates(self) -> Dict[AgentType, AgentTemplate]:
        """Load predefined agent templates"""
        templates = {
            AgentType.FRONTEND_DEVELOPER: AgentTemplate(
                type=AgentType.FRONTEND_DEVELOPER,
                name="Frontend Developer",
                description="Specializes in user interface development and user experience",
                capabilities=[
                    "react", "vue", "angular", "typescript", "javascript",
                    "html", "css", "sass", "tailwind", "ui_design",
                    "responsive_design", "accessibility", "testing"
                ],
                default_tools=["Read", "Write", "Edit", "Bash"],
                prompt_template="You are a Frontend Developer agent specializing in modern web development.",
                preferred_project_structure=[
                    "src/components/", "src/pages/", "src/hooks/", 
                    "src/utils/", "src/styles/", "public/"
                ]
            ),
            
            AgentType.BACKEND_DEVELOPER: AgentTemplate(
                type=AgentType.BACKEND_DEVELOPER,
                name="Backend Developer", 
                description="Focuses on server-side logic, APIs, and database management",
                capabilities=[
                    "python", "node.js", "java", "go", "rust",
                    "fastapi", "express", "django", "flask",
                    "postgresql", "mongodb", "redis", "api_design",
                    "microservices", "database_optimization", "security"
                ],
                default_tools=["Read", "Write", "Edit", "Bash"],
                prompt_template="You are a Backend Developer agent specializing in server-side development.",
                preferred_project_structure=[
                    "src/api/", "src/models/", "src/services/", 
                    "src/utils/", "tests/", "migrations/"
                ]
            ),
            
            AgentType.DEVOPS_ENGINEER: AgentTemplate(
                type=AgentType.DEVOPS_ENGINEER,
                name="DevOps Engineer",
                description="Handles deployment, infrastructure, and CI/CD pipelines",
                capabilities=[
                    "docker", "kubernetes", "terraform", "ansible",
                    "aws", "gcp", "azure", "ci_cd", "monitoring",
                    "logging", "security_scanning", "infrastructure_as_code"
                ],
                default_tools=["Read", "Write", "Edit", "Bash"],
                prompt_template="You are a DevOps Engineer agent specializing in infrastructure and deployment.",
                preferred_project_structure=[
                    "infrastructure/", "docker/", "k8s/", 
                    ".github/workflows/", "scripts/", "monitoring/"
                ]
            ),
            
            AgentType.QA_TESTER: AgentTemplate(
                type=AgentType.QA_TESTER,
                name="QA Tester",
                description="Ensures quality through testing and validation",
                capabilities=[
                    "manual_testing", "automated_testing", "test_planning",
                    "selenium", "cypress", "jest", "pytest", "postman",
                    "performance_testing", "security_testing", "accessibility_testing"
                ],
                default_tools=["Read", "Write", "Edit", "Bash"],
                prompt_template="You are a QA Tester agent specializing in quality assurance and testing.",
                preferred_project_structure=[
                    "tests/", "test-data/", "test-reports/", 
                    "automation/", "performance/", "security/"
                ]
            ),
            
            AgentType.TECHNICAL_WRITER: AgentTemplate(
                type=AgentType.TECHNICAL_WRITER,
                name="Technical Writer",
                description="Creates and maintains technical documentation",
                capabilities=[
                    "technical_writing", "documentation", "markdown",
                    "api_documentation", "user_guides", "tutorials",
                    "diagrams", "content_strategy", "information_architecture"
                ],
                default_tools=["Read", "Write", "Edit"],
                prompt_template="You are a Technical Writer agent specializing in clear, comprehensive documentation.",
                preferred_project_structure=[
                    "docs/", "guides/", "api/", "tutorials/", 
                    "images/", "examples/"
                ]
            )
        }
        
        return templates
    
    def _load_system_config(self) -> Dict[str, Any]:
        """Load system configuration"""
        default_config = {
            "max_concurrent_agents": 5,
            "task_timeout_minutes": 60,
            "health_check_interval": 30,
            "observability_server": "http://localhost:4000",
            "coordination_port": 4001,
            "log_level": "INFO",
            "auto_assign_tasks": True,
            "agent_restart_on_failure": True,
            "max_task_retries": 3,
            "message_retention_hours": 24,
            "workspace_base_path": ".",
            "claude_code_path": "claude-code"
        }
        
        return default_config
    
    def get_agent_template(self, agent_type: AgentType) -> Optional[AgentTemplate]:
        """Get agent template by type"""
        return self.agent_templates.get(agent_type)
    
    def create_agent_from_template(self, agent_type: AgentType, agent_id: str, 
                                 project_path: str = ".") -> Dict[str, Any]:
        """Create agent configuration from template"""
        template = self.get_agent_template(agent_type)
        if not template:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        return {
            "id": agent_id,
            "name": template.name,
            "role": template.type.value,
            "capabilities": template.capabilities,
            "project_path": project_path,
            "max_concurrent_tasks": template.max_concurrent_tasks,
            "prompt_template": template.prompt_template
        }