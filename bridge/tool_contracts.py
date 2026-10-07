"""Dedicated MCP input/output contracts. General dynamic entrypoints remain compatible."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class MolecularContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    species: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=500)
    biological_unit: str = Field(min_length=1, max_length=500)
    contrast: str = Field(min_length=1, max_length=500)
    source_version: str = Field(min_length=1, max_length=500)
    assembly: str | None = Field(default=None, max_length=100)


MolecularTask = Literal['gene_annotation','expression','single_cell','splicing','long_read_rna','chromatin','rna_binding',
                        'translation','epigenetics','regulatory_network','protein_function','proteomics','interaction',
                        'perturbation','structure_cadd','mechanism']


class ExecutionReceipt(BaseModel):
    model_config = ConfigDict(extra='allow')
    success: bool
    tool: str
    result_file: str
    receipt_file: str
    sha256: str = Field(pattern='^[a-f0-9]{64}$')
    result_preview: str
    truncated: bool
    error_type: str | None = None
    error_code: str | None = None


class Availability(BaseModel):
    model_config = ConfigDict(extra='allow')
    runtime_state: Literal['untested', 'passed', 'failed', 'expired']
    historical_success: bool
    last_attempt_success: bool | None
    current_environment_verified: bool
    validation_expired: bool
