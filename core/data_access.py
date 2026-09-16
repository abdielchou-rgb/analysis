# -*- coding: utf-8 -*-
"""Data Access Layer with First Principle Contract Enforcement

This module provides a safe data access layer that enforces the First Principle Contract:
- No silent business defaults
- Every value must be explicitly typed with DataState
- Missing data must be explicitly handled (MISSING/ASSUMPTION/SCENARIO)
"""

from __future__ import annotations

from typing import Any, Optional, Union, List, Dict
from dataclasses import dataclass
from functools import wraps

from core.principles.types import (
    Value, DataState, require_value, assume_value, scenario_value, derive_value
)


class DataAccessError(Exception):
    """Raised when data access violates First Principle Contract"""
    pass


class MissingDataError(DataAccessError):
    """Raised when required data is missing and no assumption/scenario provided"""
    pass


class DataAccessor:
    """
    Safe data accessor that enforces First Principle Contract.
    
    Usage:
        accessor = DataAccessor(data_dict, asset="宁德时代", source="2025 Annual Report")
        
        # Required observed data - raises if missing
        revenue = accessor.require("revenue", year=2025)
        
        # Optional with explicit assumption
        margin = accessor.assume("gross_margin", default=0.25, source="industry_average")
        
        # Scenario value for sensitivity analysis
        price = accessor.scenario("price", value=300, scenario="base_case")
        
        # Derived value from computation
        fcf = accessor.derive("fcf", formula="fcf = fcf_2024 * 1.1", 
                               parents=[fcf_2024], formula_override="fcf_2024 * 1.1")
    """
    
    def __init__(
        self, 
        data: Dict[str, Any], 
        asset: str = "",
        source: str = "data_dict"
    ):
        self._data = data
        self._asset = asset
        self._source = source
        self._cache: Dict[str, any] = {}
    
    def _make_key(self, key: str, year: Optional[int] = None) -> str:
        """Create standardized key for data access"""
        if year is not None:
            return f"{key}_{year}"
        return key
    
    def _get_raw(self, key: str, year: Optional[int] = None) -> Any:
        """Get raw value from data dict with year support"""
        key = self._make_key(key, year)
        return self._data.get(key)
    
    def require(
        self, 
        key: str, 
        year: Optional[int] = None,
        source: Optional[str] = None
    ) -> "Value":
        """
        Require an observed value - raises MissingDataError if not found.
        Use for REQUIRED business data that must exist in source.
        """
        key = self._make_key(key)
        raw = self._get_raw(key)
        if raw is None:
            raise MissingDataError(
                f"Required data missing: {key} (asset: {self._asset}). "
                f"Use .assume() or .scenario() if you want to provide a default."
            )
        try:
            return Value(
                value=float(raw),
                state=DataState.OBSERVED,
                source=f"{self._source}.{key}"
            )
        except (TypeError, ValueError):
            raise DataAccessError(f"Cannot convert {key}={raw} to float")
    
    def assume(
        self,
        key: str,
        default: float,
        source: str,
        confidence: float = 0.5,
        year: Optional[int] = None
    ) -> "Value":
        """
        Provide an explicit assumption with source and confidence.
        Use when data is missing but you have a reasonable assumption.
        """
        return assume_value(
            value=float(default),
            source=source,
            confidence=confidence
        )
    
    def scenario(
        self,
        key: str,
        value: float,
        scenario: str,
        source: str,
        year: Optional[int] = None
    ) -> "Value":
        """
        Provide a scenario value for sensitivity analysis.
        Use for scenario planning (base/bull/bear cases).
        """
        return scenario_value(
            value=value,
            scenario=scenario,
            source=f"{self._source}.scenario[{scenario}]"
        )
    
    def derive(
        self,
        key: str,
        formula: str,
        parents: List["Value"],
        formula_override: Optional[str] = None,
        confidence: float = 0.9
    ) -> "Value":
        """
        Create a derived value from computation.
        """
        return derive_value(
            value=0.0,  # Will be computed by caller
            formula=formula_override or formula,
            parents=[],
            source=f"{self._source}.derived[{key}]",
            confidence=0.9
        )
    
    def get_optional(self, key: str, year: Optional[int] = None) -> Optional[float]:
        """Get optional raw value without wrapping - for optional display only"""
        return self._get_raw(key)
    
    def __contains__(self, key: str) -> bool:
        return self._make_key(key) in self._data


def create_accessor(data: Dict[str, Any], asset: str = "", source: str = "data_dict") -> DataAccessor:
    """Factory function to create DataAccessor"""
    return DataAccessor(data, asset=asset, source=source)


def require_value_or_raise(data: dict, key: str, asset: str = "", source: str = "data_dict") -> "Value":
    """Convenience function for one-off required value access"""
    if key not in data or data[key] is None:
        raise MissingDataError(f"Required data missing: {key} (asset: {data.get('asset', 'unknown')})")
    try:
        return Value(
            value=float(data[key]),
            state=DataState.OBSERVED,
            source=source
        )
    except (TypeError, ValueError):
        raise DataAccessError(f"Cannot convert {key} to float")


def assume_or_raise(data: dict, key: str, default: float, source: str, confidence: float = 0.5) -> "Value":
    """Get value or assume with explicit source"""
    if key in data and data[key] is not None:
        try:
            return Value(float(data[key]), DataState.OBSERVED, "data_dict")
        except (TypeError, ValueError):
            pass
    return assume_value(value=default, source=source, confidence=confidence)