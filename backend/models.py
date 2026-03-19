"""
Project Fact Information Data Models

Defines the data structures for the three-layer project fact information system.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class FactLayer(str, Enum):
    """Enumeration for the three layers of fact information."""
    MANIFEST = "manifest"          # Layer 1: Inventory/Manifest
    CORE = "core"                  # Layer 2: Core Information
    DESIGN = "design"              # Layer 3: Design & Development


class FactCategory(str, Enum):
    """Enumeration for different categories of fact information."""
    # Layer 1: Manifest categories
    USECASES = "usecases"
    MODULES = "modules"
    USERS = "users"
    RISKS = "risks"

    # Layer 2: Core categories
    USECASE_DESCRIPTIONS = "usecase_descriptions"
    FEATURE_DESCRIPTIONS = "feature_descriptions"
    ARCHITECTURE = "architecture"
    INTERFACES = "interfaces"
    DATA_MODEL = "data_model"

    # Layer 3: Design categories
    PROTOTYPES = "prototypes"
    PRDS = "prds"
    API_DESIGN = "api_design"
    CODE_REFERENCES = "code_references"


@dataclass
class FactMetadata:
    """Metadata for a fact information item."""
    id: str                                    # Unique identifier
    name: str                                  # Display name
    description: Optional[str] = None          # Description
    layer: FactLayer = FactLayer.MANIFEST      # Which layer it belongs to
    category: FactCategory = FactCategory.USECASES  # Category within the layer
    created_at: datetime = field(default_factory=datetime.utcnow)  # Creation time
    updated_at: datetime = field(default_factory=datetime.utcnow)  # Last update time
    version: str = "1.0.0"                     # Version number
    author: Optional[str] = None               # Author/maintainer
    tags: List[str] = field(default_factory=list)  # Search tags
    related_ids: List[str] = field(default_factory=list)  # Related item IDs
    source_file: Optional[str] = None          # Source file path


@dataclass
class FactInformation:
    """Core fact information item."""
    metadata: FactMetadata
    content: str                               # Main content (Markdown format)
    raw_data: Dict[str, Any] = field(default_factory=dict)  # Structured data (JSON/YAML)
    relationships: Dict[str, List[str]] = field(default_factory=dict)  # Links to other items
    status: str = "active"                     # active, deprecated, draft


@dataclass
class UseCase:
    """Use case information."""
    id: str
    name: str
    description: str
    actors: List[str]  # System actors/users involved
    preconditions: List[str]
    main_flow: List[str]
    alternative_flows: Dict[str, List[str]] = field(default_factory=dict)
    postconditions: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class Module:
    """Module/Component information."""
    id: str
    name: str
    description: str
    parent_id: Optional[str] = None  # For hierarchical modules
    submodules: List[str] = field(default_factory=list)  # Child modules
    interfaces: List[str] = field(default_factory=list)  # Provided interfaces
    dependencies: List[str] = field(default_factory=list)  # Dependent modules
    technology_stack: List[str] = field(default_factory=list)  # Tech used
    team: Optional[str] = None  # Responsible team


@dataclass
class Interface:
    """Interface/API endpoint information."""
    id: str
    name: str
    module_id: str  # Which module provides this
    endpoint: str  # API endpoint (e.g., POST /api/v1/auth/login)
    description: str
    input_schema: Dict[str, Any] = field(default_factory=dict)  # Input parameters
    output_schema: Dict[str, Any] = field(default_factory=dict)  # Response format
    error_codes: Dict[str, str] = field(default_factory=dict)  # Possible errors
    authentication: Optional[str] = None  # Auth requirements
    rate_limit: Optional[str] = None  # Rate limiting info


@dataclass
class DataEntity:
    """Data model entity information."""
    id: str
    name: str
    description: str
    fields: Dict[str, str] = field(default_factory=dict)  # field_name: field_type
    primary_key: Optional[str] = None
    indexes: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)  # Relationships to other entities
    constraints: List[str] = field(default_factory=list)


@dataclass
class FactInformationQuery:
    """Query parameters for fact information retrieval."""
    layer: Optional[FactLayer] = None
    category: Optional[FactCategory] = None
    id: Optional[str] = None
    keyword: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    limit: int = 100
    offset: int = 0


@dataclass
class FactInformationResult:
    """Result of a fact information query."""
    items: List[FactInformation]
    total_count: int
    query: FactInformationQuery
    related_items: Dict[str, List[FactInformation]] = field(default_factory=dict)


# Database schema representation
@dataclass
class FactInformationSchema:
    """Schema for storing fact information in a database/file system."""
    version: str = "1.0"
    layers: Dict[FactLayer, Dict[FactCategory, List[FactInformation]]] = field(
        default_factory=lambda: {
            FactLayer.MANIFEST: {},
            FactLayer.CORE: {},
            FactLayer.DESIGN: {}
        }
    )
    indexes: Dict[str, List[str]] = field(default_factory=dict)  # For fast lookup
    last_updated: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata


# Helper functions for creating instances

def create_usecase(
    id: str,
    name: str,
    description: str,
    actors: List[str],
    main_flow: List[str],
    **kwargs
) -> UseCase:
    """Create a UseCase instance."""
    return UseCase(
        id=id,
        name=name,
        description=description,
        actors=actors,
        main_flow=main_flow,
        preconditions=kwargs.get('preconditions', []),
        alternative_flows=kwargs.get('alternative_flows', {}),
        postconditions=kwargs.get('postconditions', []),
        notes=kwargs.get('notes')
    )


def create_module(
    id: str,
    name: str,
    description: str,
    **kwargs
) -> Module:
    """Create a Module instance."""
    return Module(
        id=id,
        name=name,
        description=description,
        parent_id=kwargs.get('parent_id'),
        submodules=kwargs.get('submodules', []),
        interfaces=kwargs.get('interfaces', []),
        dependencies=kwargs.get('dependencies', []),
        technology_stack=kwargs.get('technology_stack', []),
        team=kwargs.get('team')
    )


def create_interface(
    id: str,
    name: str,
    module_id: str,
    endpoint: str,
    description: str,
    **kwargs
) -> Interface:
    """Create an Interface instance."""
    return Interface(
        id=id,
        name=name,
        module_id=module_id,
        endpoint=endpoint,
        description=description,
        input_schema=kwargs.get('input_schema', {}),
        output_schema=kwargs.get('output_schema', {}),
        error_codes=kwargs.get('error_codes', {}),
        authentication=kwargs.get('authentication'),
        rate_limit=kwargs.get('rate_limit')
    )
