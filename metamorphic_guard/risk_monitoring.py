"""
Risk monitoring and alerting for Metamorphic Guard.

Tracks risk indicators and triggers alerts when thresholds are exceeded.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .types import JSONDict


class RiskLevel(Enum):
    """Risk severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskCategory(Enum):
    """Categories of risks."""

    TYPE_SAFETY = "type_safety"
    API_COMPATIBILITY = "api_compatibility"
    STATISTICAL_ACCURACY = "statistical_accuracy"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ADOPTION = "adoption"
    MAINTENANCE = "maintenance"
    DEPENDENCIES = "dependencies"


@dataclass
class RiskIndicator:
    """A risk indicator with current value and thresholds."""

    category: RiskCategory
    name: str
    current_value: float
    warning_threshold: float
    critical_threshold: float
    unit: str = ""
    description: str = ""

    def get_level(self) -> RiskLevel:
        """Get current risk level based on thresholds."""
        if self.current_value >= self.critical_threshold:
            return RiskLevel.CRITICAL
        elif self.current_value >= self.warning_threshold:
            return RiskLevel.HIGH
        elif self.current_value >= self.warning_threshold * 0.7:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


@dataclass
class RiskAlert:
    """A risk alert triggered by an indicator."""

    indicator: RiskIndicator
    level: RiskLevel
    timestamp: float
    message: str
    recommendations: List[str] = field(default_factory=list)


class RiskMonitor:
    """Monitor for tracking risk indicators and generating alerts."""

    def __init__(self) -> None:
        """Initialize risk monitor."""
        self.indicators: Dict[str, RiskIndicator] = {}
        self.alerts: List[RiskAlert] = []
        self.alert_callbacks: List[callable] = []

    def register_indicator(
        self,
        category: RiskCategory,
        name: str,
        warning_threshold: float,
        critical_threshold: float,
        unit: str = "",
        description: str = "",
    ) -> None:
        """
        Register a risk indicator.

        Args:
            category: Risk category
            name: Indicator name (must be unique)
            warning_threshold: Value at which to trigger warning
            critical_threshold: Value at which to trigger critical alert
            unit: Unit of measurement
            description: Description of the indicator
        """
        indicator = RiskIndicator(
            category=category,
            name=name,
            current_value=0.0,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            unit=unit,
            description=description,
        )
        self.indicators[name] = indicator

    def update_indicator(self, name: str, value: float) -> Optional[RiskAlert]:
        """
        Update an indicator value and check for alerts.

        Args:
            name: Indicator name
            value: New value

        Returns:
            RiskAlert if threshold exceeded, None otherwise
        """
        if name not in self.indicators:
            raise ValueError(f"Indicator '{name}' not registered")

        indicator = self.indicators[name]
        indicator.current_value = value

        level = indicator.get_level()
        if level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            alert = self._create_alert(indicator, level)
            self.alerts.append(alert)

            # Trigger callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    print(f"Warning: Risk alert callback failed: {e}")

            return alert

        return None

    def _create_alert(self, indicator: RiskIndicator, level: RiskLevel) -> RiskAlert:
        """Create a risk alert from an indicator."""
        message = (
            f"{indicator.category.value.upper()}: {indicator.name} = "
            f"{indicator.current_value}{indicator.unit} "
            f"(threshold: {indicator.warning_threshold}{indicator.unit})"
        )

        recommendations = self._get_recommendations(indicator, level)

        return RiskAlert(
            indicator=indicator,
            level=level,
            timestamp=time.time(),
            message=message,
            recommendations=recommendations,
        )

    def _get_recommendations(
        self,
        indicator: RiskIndicator,
        level: RiskLevel,
    ) -> List[str]:
        """Get recommendations for addressing a risk indicator."""
        recommendations = []

        if indicator.category == RiskCategory.TYPE_SAFETY:
            if indicator.name == "any_usage_count":
                recommendations.append("Review and migrate Any types to specific types")
                recommendations.append("Run type safety audit")
            elif indicator.name == "mypy_errors":
                recommendations.append("Fix mypy errors in CI/CD")
                recommendations.append("Review type annotations")

        elif indicator.category == RiskCategory.API_COMPATIBILITY:
            recommendations.append("Check provider API changelogs")
            recommendations.append("Update executor implementations if needed")
            recommendations.append("Test with latest API versions")

        elif indicator.category == RiskCategory.STATISTICAL_ACCURACY:
            recommendations.append("Review statistical method implementation")
            recommendations.append("Validate against known benchmarks")
            recommendations.append("Check CI coverage")

        elif indicator.category == RiskCategory.PERFORMANCE:
            recommendations.append("Profile hot paths")
            recommendations.append("Optimize identified bottlenecks")
            recommendations.append("Consider distributed execution")

        elif indicator.category == RiskCategory.SECURITY:
            recommendations.append("Review security advisories")
            recommendations.append("Update vulnerable dependencies")
            recommendations.append("Conduct security audit")

        elif indicator.category == RiskCategory.DEPENDENCIES:
            recommendations.append("Update dependencies")
            recommendations.append("Review changelogs for breaking changes")
            recommendations.append("Test compatibility")

        return recommendations

    def register_alert_callback(self, callback: callable) -> None:
        """
        Register a callback to be invoked when alerts are triggered.

        Args:
            callback: Function that takes a RiskAlert as argument
        """
        self.alert_callbacks.append(callback)

    def get_alerts(
        self,
        category: Optional[RiskCategory] = None,
        level: Optional[RiskLevel] = None,
        since: Optional[float] = None,
    ) -> List[RiskAlert]:
        """
        Get alerts matching criteria.

        Args:
            category: Filter by category
            level: Filter by level
            since: Filter alerts after this timestamp

        Returns:
            List of matching alerts
        """
        filtered = self.alerts

        if category:
            filtered = [a for a in filtered if a.indicator.category == category]

        if level:
            filtered = [a for a in filtered if a.level == level]

        if since:
            filtered = [a for a in filtered if a.timestamp >= since]

        return filtered

    def get_indicators(self, category: Optional[RiskCategory] = None) -> List[RiskIndicator]:
        """
        Get all indicators, optionally filtered by category.

        Args:
            category: Filter by category

        Returns:
            List of indicators
        """
        if category:
            return [i for i in self.indicators.values() if i.category == category]
        return list(self.indicators.values())

    def get_summary(self) -> JSONDict:
        """Get summary of current risk status."""
        summary: JSONDict = {
            "total_indicators": len(self.indicators),
            "total_alerts": len(self.alerts),
            "alerts_by_level": {},
            "alerts_by_category": {},
            "indicators_by_level": {},
        }

        # Count alerts by level
        for level in RiskLevel:
            count = len([a for a in self.alerts if a.level == level])
            summary["alerts_by_level"][level.value] = count

        # Count alerts by category
        for category in RiskCategory:
            count = len([a for a in self.alerts if a.indicator.category == category])
            summary["alerts_by_category"][category.value] = count

        # Count indicators by level
        for level in RiskLevel:
            count = len([i for i in self.indicators.values() if i.get_level() == level])
            summary["indicators_by_level"][level.value] = count

        return summary


# Global risk monitor instance
_global_risk_monitor: Optional[RiskMonitor] = None


def get_risk_monitor() -> RiskMonitor:
    """Get the global risk monitor instance."""
    global _global_risk_monitor
    if _global_risk_monitor is None:
        _global_risk_monitor = RiskMonitor()
        _initialize_default_indicators(_global_risk_monitor)
    return _global_risk_monitor


def _initialize_default_indicators(monitor: RiskMonitor) -> None:
    """Initialize default risk indicators."""
    # Type safety indicators
    monitor.register_indicator(
        RiskCategory.TYPE_SAFETY,
        "any_usage_count",
        warning_threshold=50.0,
        critical_threshold=100.0,
        unit="",
        description="Number of Any type usages in codebase",
    )
    monitor.register_indicator(
        RiskCategory.TYPE_SAFETY,
        "mypy_errors",
        warning_threshold=10.0,
        critical_threshold=50.0,
        unit="",
        description="Number of mypy type errors",
    )

    # API compatibility indicators
    monitor.register_indicator(
        RiskCategory.API_COMPATIBILITY,
        "executor_error_rate",
        warning_threshold=0.05,
        critical_threshold=0.10,
        unit="",
        description="Fraction of executor calls that fail",
    )

    # Performance indicators
    monitor.register_indicator(
        RiskCategory.PERFORMANCE,
        "avg_execution_time_ms",
        warning_threshold=5000.0,
        critical_threshold=10000.0,
        unit="ms",
        description="Average execution time per test case",
    )

    # Security indicators
    monitor.register_indicator(
        RiskCategory.SECURITY,
        "cve_count",
        warning_threshold=5.0,
        critical_threshold=10.0,
        unit="",
        description="Number of known CVEs in dependencies",
    )

    # Dependency indicators
    monitor.register_indicator(
        RiskCategory.DEPENDENCIES,
        "outdated_dependencies",
        warning_threshold=10.0,
        critical_threshold=20.0,
        unit="",
        description="Number of outdated dependencies",
    )

