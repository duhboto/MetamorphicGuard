"""
Trade-off visualization for multi-objective optimization results.

This module provides utilities for visualizing Pareto frontiers and trade-offs
between different objectives.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .multi_objective import CandidateMetrics, MultiObjectiveConfig, analyze_trade_offs
from .types import JSONDict


def format_pareto_frontier(
    analysis: Dict[str, Any],
    format: str = "text",
) -> str:
    """
    Format Pareto frontier for display.
    
    Args:
        analysis: Results from analyze_trade_offs
        format: Output format ("text", "json", "markdown")
    
    Returns:
        Formatted string representation
    """
    pareto_frontier = analysis.get("pareto_frontier", [])
    pareto_optimal = analysis.get("pareto_optimal", [])
    objectives = analysis.get("objectives", [])
    
    if format == "json":
        import json
        return json.dumps(analysis, indent=2)
    
    if format == "markdown":
        lines = ["# Pareto Frontier Analysis\n"]
        lines.append(f"**Objectives**: {', '.join(objectives)}\n")
        lines.append(f"**Pareto-Optimal Candidates**: {len(pareto_optimal)}\n\n")
        
        lines.append("## Pareto-Optimal Candidates\n")
        for point in pareto_frontier:
            if not point.get("dominated", False):
                lines.append(f"### {point['candidate_id']}\n")
                for obj_name, value in point["objectives"].items():
                    lines.append(f"- {obj_name}: {value:.4f}\n")
                lines.append("\n")
        
        return "".join(lines)
    
    # Text format (default)
    lines = ["Pareto Frontier Analysis"]
    lines.append("=" * 60)
    lines.append(f"Objectives: {', '.join(objectives)}")
    lines.append(f"Pareto-Optimal Candidates: {len(pareto_optimal)}")
    lines.append("")
    
    lines.append("Pareto-Optimal Points:")
    for point in pareto_frontier:
        if not point.get("dominated", False):
            lines.append(f"  {point['candidate_id']}:")
            for obj_name, value in point["objectives"].items():
                lines.append(f"    {obj_name}: {value:.4f}")
    
    return "\n".join(lines)


def create_trade_off_chart_data(
    analysis: Dict[str, Any],
    objective_x: str,
    objective_y: str,
) -> Dict[str, Any]:
    """
    Create data for a 2D trade-off chart.
    
    Args:
        analysis: Results from analyze_trade_offs
        objective_x: Objective for X-axis
        objective_y: Objective for Y-axis
    
    Returns:
        Chart data dictionary
    """
    pareto_frontier = analysis.get("pareto_frontier", [])
    
    points = []
    pareto_points = []
    
    for point in pareto_frontier:
        x_val = point["objectives"].get(objective_x, 0.0)
        y_val = point["objectives"].get(objective_y, 0.0)
        
        point_data = {
            "candidate_id": point["candidate_id"],
            "x": x_val,
            "y": y_val,
            "dominated": point.get("dominated", False),
        }
        
        points.append(point_data)
        
        if not point.get("dominated", False):
            pareto_points.append(point_data)
    
    return {
        "objective_x": objective_x,
        "objective_y": objective_y,
        "all_points": points,
        "pareto_points": pareto_points,
        "format": "chart_data",
    }


def generate_recommendation_report(
    candidates: List[CandidateMetrics],
    config: MultiObjectiveConfig,
    recommended_id: Optional[str] = None,
) -> str:
    """
    Generate a human-readable recommendation report.
    
    Args:
        candidates: List of candidate metrics
        config: Multi-objective configuration
        recommended_id: Recommended candidate ID (if None, will compute)
    
    Returns:
        Formatted report string
    """
    if recommended_id is None:
        from .multi_objective import recommend_candidate
        recommended_id = recommend_candidate(candidates, config)
    
    analysis = analyze_trade_offs(candidates, config)
    
    lines = ["Multi-Objective Recommendation Report"]
    lines.append("=" * 60)
    lines.append("")
    
    lines.append("Objectives:")
    for obj_name in config.objectives:
        weight = config.weights.get(obj_name, 1.0) if config.weights else 1.0
        minimize = config.minimize.get(obj_name, False) if config.minimize else False
        direction = "minimize" if minimize else "maximize"
        lines.append(f"  - {obj_name}: {direction} (weight: {weight:.2f})")
    lines.append("")
    
    lines.append("Pareto-Optimal Candidates:")
    pareto_optimal = analysis.get("pareto_optimal", [])
    for cand_id in pareto_optimal:
        lines.append(f"  - {cand_id}")
    lines.append("")
    
    if recommended_id:
        lines.append(f"Recommended Candidate: {recommended_id}")
        lines.append("")
        
        # Show metrics for recommended candidate
        recommended = next(
            (c for c in candidates if c.candidate_id == recommended_id),
            None
        )
        if recommended:
            lines.append("Metrics:")
            for obj_name in config.objectives:
                if obj_name in recommended.objectives:
                    obj = recommended.objectives[obj_name]
                    threshold = config.thresholds.get(obj_name) if config.thresholds else None
                    threshold_str = f" (threshold: {threshold:.4f})" if threshold else ""
                    lines.append(f"  - {obj_name}: {obj.value:.4f}{threshold_str}")
    else:
        lines.append("No candidate meets all thresholds.")
    
    lines.append("")
    lines.append("Trade-off Analysis:")
    trade_off_matrix = analysis.get("trade_off_matrix", {})
    if trade_off_matrix and recommended_id:
        if recommended_id in trade_off_matrix:
            for other_id, diffs in trade_off_matrix[recommended_id].items():
                if other_id != recommended_id:
                    lines.append(f"  vs {other_id}:")
                    for obj_name, diff in diffs.items():
                        lines.append(f"    {obj_name}: {diff:+.2%}")
    
    return "\n".join(lines)


def export_pareto_data(
    analysis: Dict[str, Any],
    format: str = "json",
) -> str:
    """
    Export Pareto frontier data in various formats.
    
    Args:
        analysis: Results from analyze_trade_offs
        format: Export format ("json", "csv", "html")
    
    Returns:
        Exported data as string
    """
    pareto_frontier = analysis.get("pareto_frontier", [])
    objectives = analysis.get("objectives", [])
    
    if format == "json":
        import json
        return json.dumps(analysis, indent=2)
    
    if format == "csv":
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        header = ["candidate_id", "rank", "dominated"] + objectives
        writer.writerow(header)
        
        # Data rows
        for point in pareto_frontier:
            row = [
                point["candidate_id"],
                point.get("rank", 0),
                point.get("dominated", False),
            ]
            for obj_name in objectives:
                row.append(point["objectives"].get(obj_name, 0.0))
            writer.writerow(row)
        
        return output.getvalue()
    
    if format == "html":
        # Generate simple HTML table
        html = ["<table>"]
        html.append("<thead><tr>")
        html.append("<th>Candidate</th><th>Rank</th><th>Dominated</th>")
        for obj_name in objectives:
            html.append(f"<th>{obj_name}</th>")
        html.append("</tr></thead>")
        html.append("<tbody>")
        
        for point in pareto_frontier:
            html.append("<tr>")
            html.append(f"<td>{point['candidate_id']}</td>")
            html.append(f"<td>{point.get('rank', 0)}</td>")
            html.append(f"<td>{point.get('dominated', False)}</td>")
            for obj_name in objectives:
                value = point["objectives"].get(obj_name, 0.0)
                html.append(f"<td>{value:.4f}</td>")
            html.append("</tr>")
        
        html.append("</tbody></table>")
        return "".join(html)
    
    return str(analysis)

