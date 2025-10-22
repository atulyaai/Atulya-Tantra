"""
Data Agent for Atulya Tantra AGI
Specialized agent for data analysis, processing, and visualization
"""

import json
import csv
import io
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import statistics
import math

from .base_agent import BaseAgent, AgentTask, AgentCapability, AgentStatus
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router

logger = get_logger(__name__)


class DataAgent(BaseAgent):
    """Agent specialized in data analysis, processing, and visualization"""
    
    def __init__(self):
        super().__init__(
            name="DataAgent",
            description="Specialized agent for data analysis, processing, visualization, and statistical operations",
            capabilities=[
                AgentCapability.DATA_ANALYSIS,
                AgentCapability.FILE_PROCESSING,
                AgentCapability.TEXT_GENERATION
            ],
            max_concurrent_tasks=2,
            timeout_seconds=300
        )
        
        self.supported_formats = ["json", "csv", "xml", "txt", "xlsx"]
        self.max_data_size = 10000  # Maximum number of data points to process
        self.statistical_methods = [
            "mean", "median", "mode", "std", "variance", "range", "percentile",
            "correlation", "regression", "distribution", "outlier_detection"
        ]
    
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task"""
        task_type = task.task_type or ""
        description = (task.description or "").lower()
        
        # Check for data-related keywords
        data_keywords = [
            "data", "analysis", "statistics", "chart", "graph", "visualization",
            "csv", "json", "excel", "spreadsheet", "dataset", "metrics",
            "calculate", "compute", "process", "transform", "aggregate",
            "trend", "pattern", "correlation", "regression", "outlier",
            "summary", "report", "insights", "dashboard", "table"
        ]
        
        return (
            task_type in ["data_analysis", "data_processing", "data_visualization", "statistics"] or
            any(keyword in description for keyword in data_keywords)
        )
    
    async def get_task_estimate(self, task: AgentTask) -> Dict[str, Any]:
        """Estimate task execution time and resource requirements"""
        task_type = task.task_type or ""
        input_data = task.input_data or {}
        
        # Base estimates
        if task_type == "data_analysis":
            estimated_time = 60  # seconds
            complexity = "medium"
        elif task_type == "data_processing":
            estimated_time = 45
            complexity = "medium"
        elif task_type == "data_visualization":
            estimated_time = 90
            complexity = "high"
        else:
            estimated_time = 75
            complexity = "medium"
        
        # Adjust based on data size
        data_size = self._estimate_data_size(input_data)
        if data_size > 1000:
            estimated_time *= 1.5
            complexity = "high"
        elif data_size < 100:
            estimated_time *= 0.7
            complexity = "low"
        
        return {
            "estimated_time_seconds": estimated_time,
            "complexity": complexity,
            "resource_requirements": {
                "memory_mb": 100 + (data_size * 0.1),
                "cpu_usage": "medium",
                "data_size": data_size
            }
        }
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a data-related task"""
        try:
            task_type = task.task_type or "data_analysis"
            input_data = task.input_data or {}
            
            if task_type == "data_analysis":
                return await self._analyze_data(task, input_data)
            elif task_type == "data_processing":
                return await self._process_data(task, input_data)
            elif task_type == "data_visualization":
                return await self._create_visualization(task, input_data)
            elif task_type == "statistics":
                return await self._calculate_statistics(task, input_data)
            elif task_type == "data_transformation":
                return await self._transform_data(task, input_data)
            else:
                return await self._general_data_task(task, input_data)
                
        except Exception as e:
            logger.error(f"DataAgent execution error: {e}")
            raise AgentError(f"Data task failed: {e}")
    
    async def _analyze_data(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive data analysis"""
        data = input_data.get("data", [])
        analysis_type = input_data.get("analysis_type", "comprehensive")
        columns = input_data.get("columns", [])
        
        if not data:
            raise AgentError("No data provided for analysis")
        
        # Validate data size
        if len(data) > self.max_data_size:
            raise AgentError(f"Data too large. Maximum {self.max_data_size} records supported.")
        
        analysis_results = {
            "data_overview": await self._get_data_overview(data, columns),
            "statistical_summary": await self._calculate_basic_statistics(data, columns),
            "data_quality": await self._assess_data_quality(data),
            "patterns_and_trends": await self._identify_patterns(data, columns),
            "insights": await self._generate_insights(data, analysis_type),
            "recommendations": await self._generate_recommendations(data),
            "metadata": {
                "task_type": "data_analysis",
                "analyzed_at": datetime.utcnow().isoformat(),
                "data_size": len(data),
                "analysis_type": analysis_type
            }
        }
        
        return analysis_results
    
    async def _process_data(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and transform data"""
        data = input_data.get("data", [])
        operations = input_data.get("operations", [])
        output_format = input_data.get("output_format", "json")
        
        if not data:
            raise AgentError("No data provided for processing")
        
        processed_data = data.copy()
        
        # Apply operations
        for operation in operations:
            processed_data = await self._apply_operation(processed_data, operation)
        
        # Convert to requested format
        formatted_data = await self._format_data(processed_data, output_format)
        
        return {
            "processed_data": formatted_data,
            "operations_applied": operations,
            "original_size": len(data),
            "processed_size": len(processed_data),
            "output_format": output_format,
            "metadata": {
                "task_type": "data_processing",
                "processed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _create_visualization(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create data visualizations and charts"""
        data = input_data.get("data", [])
        chart_type = input_data.get("chart_type", "bar")
        columns = input_data.get("columns", [])
        title = input_data.get("title", "Data Visualization")
        
        if not data:
            raise AgentError("No data provided for visualization")
        
        # Generate visualization description
        visualization_prompt = f"""
Create a detailed description for a {chart_type} chart with the following data:

Data Sample: {json.dumps(data[:10], indent=2)}
Chart Type: {chart_type}
Title: {title}
Columns: {columns}

Please provide:
1. Chart configuration details
2. Data mapping instructions
3. Color scheme recommendations
4. Axis labels and formatting
5. Legend information
6. Interactive features (if applicable)

Make it suitable for implementation in a charting library.
"""
        
        chart_description = await generate_response(
            prompt=visualization_prompt,
            max_tokens=800,
            temperature=0.3,
            preferred_provider="openai"
        )
        
        # Generate chart configuration
        chart_config = await self._generate_chart_config(data, chart_type, columns)
        
        return {
            "chart_description": chart_description,
            "chart_config": chart_config,
            "chart_type": chart_type,
            "title": title,
            "data_points": len(data),
            "metadata": {
                "task_type": "data_visualization",
                "created_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _calculate_statistics(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate statistical measures"""
        data = input_data.get("data", [])
        columns = input_data.get("columns", [])
        statistics_requested = input_data.get("statistics", ["mean", "median", "std"])
        
        if not data:
            raise AgentError("No data provided for statistical analysis")
        
        results = {}
        
        # Calculate statistics for each numeric column
        for column in columns:
            if self._is_numeric_column(data, column):
                column_data = [row.get(column) for row in data if row.get(column) is not None]
                if column_data:
                    results[column] = await self._calculate_column_statistics(column_data, statistics_requested)
        
        # Calculate overall statistics
        results["overall"] = await self._calculate_overall_statistics(data, columns)
        
        return {
            "statistics": results,
            "columns_analyzed": columns,
            "statistics_requested": statistics_requested,
            "data_size": len(data),
            "metadata": {
                "task_type": "statistics",
                "calculated_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _transform_data(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data structure or format"""
        data = input_data.get("data", [])
        transformation_type = input_data.get("transformation_type", "normalize")
        parameters = input_data.get("parameters", {})
        
        if not data:
            raise AgentError("No data provided for transformation")
        
        transformed_data = await self._apply_transformation(data, transformation_type, parameters)
        
        return {
            "transformed_data": transformed_data,
            "transformation_type": transformation_type,
            "parameters": parameters,
            "original_size": len(data),
            "transformed_size": len(transformed_data),
            "metadata": {
                "task_type": "data_transformation",
                "transformed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _general_data_task(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general data-related tasks"""
        description = task.description or ""
        
        prompt = f"""
You are a data analysis expert. Help with the following data task:

Task: {description}

Please provide:
1. Recommended approach and methodology
2. Required tools and techniques
3. Key considerations and challenges
4. Expected outcomes and deliverables
5. Best practices and tips

Be thorough and professional in your data analysis guidance.
"""
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=1000,
            temperature=0.3,
            preferred_provider="openai"
        )
        
        return {
            "data_guidance": response,
            "task_description": description,
            "metadata": {
                "task_type": "general_data_task",
                "completed_at": datetime.utcnow().isoformat()
            }
        }
    
    def _estimate_data_size(self, input_data: Dict[str, Any]) -> int:
        """Estimate the size of data to be processed"""
        data = input_data.get("data", [])
        if isinstance(data, list):
            return len(data)
        elif isinstance(data, str):
            return len(data.split('\n'))
        else:
            return 0
    
    async def _get_data_overview(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        """Get overview of the dataset"""
        if not data:
            return {}
        
        # Determine columns if not provided
        if not columns and data:
            columns = list(data[0].keys()) if data else []
        
        overview = {
            "total_records": len(data),
            "total_columns": len(columns),
            "columns": columns,
            "data_types": {},
            "sample_records": data[:3] if data else []
        }
        
        # Determine data types
        for column in columns:
            if data:
                sample_values = [row.get(column) for row in data[:10] if row.get(column) is not None]
                overview["data_types"][column] = self._infer_data_type(sample_values)
        
        return overview
    
    def _infer_data_type(self, values: List[Any]) -> str:
        """Infer data type from sample values"""
        if not values:
            return "unknown"
        
        # Check if all values are numeric
        try:
            [float(v) for v in values]
            return "numeric"
        except (ValueError, TypeError):
            pass
        
        # Check if all values are dates
        try:
            [datetime.fromisoformat(str(v)) for v in values]
            return "datetime"
        except (ValueError, TypeError):
            pass
        
        # Check if all values are booleans
        if all(str(v).lower() in ['true', 'false', '1', '0', 'yes', 'no'] for v in values):
            return "boolean"
        
        return "text"
    
    async def _calculate_basic_statistics(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        """Calculate basic statistical measures"""
        stats = {}
        
        for column in columns:
            if self._is_numeric_column(data, column):
                column_data = [row.get(column) for row in data if row.get(column) is not None]
                if column_data:
                    stats[column] = {
                        "count": len(column_data),
                        "mean": statistics.mean(column_data),
                        "median": statistics.median(column_data),
                        "mode": statistics.mode(column_data) if len(set(column_data)) < len(column_data) else None,
                        "std": statistics.stdev(column_data) if len(column_data) > 1 else 0,
                        "min": min(column_data),
                        "max": max(column_data),
                        "range": max(column_data) - min(column_data)
                    }
        
        return stats
    
    def _is_numeric_column(self, data: List[Dict], column: str) -> bool:
        """Check if a column contains numeric data"""
        if not data:
            return False
        
        sample_values = [row.get(column) for row in data[:10] if row.get(column) is not None]
        if not sample_values:
            return False
        
        try:
            [float(v) for v in sample_values]
            return True
        except (ValueError, TypeError):
            return False
    
    async def _assess_data_quality(self, data: List[Dict]) -> Dict[str, Any]:
        """Assess the quality of the dataset"""
        if not data:
            return {"quality_score": 0, "issues": ["No data provided"]}
        
        issues = []
        quality_score = 100
        
        # Check for missing values
        total_cells = len(data) * len(data[0].keys()) if data else 0
        missing_cells = sum(1 for row in data for value in row.values() if value is None or value == "")
        
        if missing_cells > 0:
            missing_percentage = (missing_cells / total_cells) * 100
            issues.append(f"{missing_percentage:.1f}% missing values")
            quality_score -= missing_percentage * 0.5
        
        # Check for duplicates
        unique_rows = len(set(str(row) for row in data))
        if unique_rows < len(data):
            duplicate_percentage = ((len(data) - unique_rows) / len(data)) * 100
            issues.append(f"{duplicate_percentage:.1f}% duplicate rows")
            quality_score -= duplicate_percentage * 0.3
        
        # Check for outliers (simplified)
        for column in data[0].keys() if data else []:
            if self._is_numeric_column(data, column):
                column_data = [row.get(column) for row in data if row.get(column) is not None]
                if column_data:
                    mean_val = statistics.mean(column_data)
                    std_val = statistics.stdev(column_data) if len(column_data) > 1 else 0
                    outliers = [v for v in column_data if abs(v - mean_val) > 3 * std_val]
                    if outliers:
                        outlier_percentage = (len(outliers) / len(column_data)) * 100
                        if outlier_percentage > 5:  # More than 5% outliers
                            issues.append(f"High outlier percentage in {column}: {outlier_percentage:.1f}%")
                            quality_score -= outlier_percentage * 0.2
        
        return {
            "quality_score": max(0, quality_score),
            "issues": issues,
            "total_records": len(data),
            "missing_values": missing_cells,
            "duplicate_rows": len(data) - unique_rows if data else 0
        }
    
    async def _identify_patterns(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        """Identify patterns and trends in the data"""
        patterns = {
            "trends": [],
            "correlations": [],
            "distributions": {},
            "seasonality": []
        }
        
        # Simple trend analysis
        for column in columns:
            if self._is_numeric_column(data, column):
                column_data = [row.get(column) for row in data if row.get(column) is not None]
                if len(column_data) > 1:
                    # Calculate simple trend
                    first_half = column_data[:len(column_data)//2]
                    second_half = column_data[len(column_data)//2:]
                    
                    first_mean = statistics.mean(first_half)
                    second_mean = statistics.mean(second_half)
                    
                    if second_mean > first_mean * 1.1:
                        patterns["trends"].append(f"{column}: Increasing trend")
                    elif second_mean < first_mean * 0.9:
                        patterns["trends"].append(f"{column}: Decreasing trend")
        
        return patterns
    
    async def _generate_insights(self, data: List[Dict], analysis_type: str) -> List[str]:
        """Generate insights from the data"""
        insights = []
        
        if not data:
            return ["No data available for analysis"]
        
        # Generate insights based on data characteristics
        total_records = len(data)
        insights.append(f"Dataset contains {total_records} records")
        
        # Check for numeric columns
        numeric_columns = [col for col in data[0].keys() if self._is_numeric_column(data, col)]
        if numeric_columns:
            insights.append(f"Found {len(numeric_columns)} numeric columns: {', '.join(numeric_columns)}")
        
        # Check for missing data
        missing_data = sum(1 for row in data for value in row.values() if value is None or value == "")
        if missing_data > 0:
            missing_percentage = (missing_data / (len(data) * len(data[0].keys()))) * 100
            insights.append(f"Data completeness: {100-missing_percentage:.1f}%")
        
        return insights
    
    async def _generate_recommendations(self, data: List[Dict]) -> List[str]:
        """Generate recommendations based on data analysis"""
        recommendations = []
        
        if not data:
            return ["Provide data for analysis"]
        
        # Data quality recommendations
        missing_data = sum(1 for row in data for value in row.values() if value is None or value == "")
        if missing_data > 0:
            recommendations.append("Consider data cleaning to handle missing values")
        
        # Size recommendations
        if len(data) < 100:
            recommendations.append("Consider collecting more data for better statistical significance")
        elif len(data) > 10000:
            recommendations.append("Consider data sampling for faster analysis")
        
        # Column recommendations
        numeric_columns = [col for col in data[0].keys() if self._is_numeric_column(data, col)]
        if len(numeric_columns) > 5:
            recommendations.append("Consider dimensionality reduction techniques")
        
        return recommendations
    
    async def _apply_operation(self, data: List[Dict], operation: Dict[str, Any]) -> List[Dict]:
        """Apply a data operation"""
        op_type = operation.get("type", "")
        
        if op_type == "filter":
            return await self._filter_data(data, operation.get("condition", {}))
        elif op_type == "sort":
            return await self._sort_data(data, operation.get("column", ""), operation.get("ascending", True))
        elif op_type == "group":
            return await self._group_data(data, operation.get("column", ""))
        elif op_type == "aggregate":
            return await self._aggregate_data(data, operation.get("group_by", ""), operation.get("aggregations", {}))
        else:
            return data
    
    async def _filter_data(self, data: List[Dict], condition: Dict[str, Any]) -> List[Dict]:
        """Filter data based on condition"""
        # Simplified filtering - in production, this would be more sophisticated
        filtered_data = []
        for row in data:
            if self._evaluate_condition(row, condition):
                filtered_data.append(row)
        return filtered_data
    
    def _evaluate_condition(self, row: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """Evaluate a condition against a row"""
        # Simplified condition evaluation
        column = condition.get("column", "")
        operator = condition.get("operator", "==")
        value = condition.get("value")
        
        if column not in row:
            return False
        
        row_value = row[column]
        
        if operator == "==":
            return row_value == value
        elif operator == "!=":
            return row_value != value
        elif operator == ">":
            return row_value > value
        elif operator == "<":
            return row_value < value
        elif operator == ">=":
            return row_value >= value
        elif operator == "<=":
            return row_value <= value
        else:
            return False
    
    async def _sort_data(self, data: List[Dict], column: str, ascending: bool = True) -> List[Dict]:
        """Sort data by column"""
        if not data or column not in data[0]:
            return data
        
        return sorted(data, key=lambda x: x.get(column, 0), reverse=not ascending)
    
    async def _group_data(self, data: List[Dict], column: str) -> Dict[str, List[Dict]]:
        """Group data by column"""
        grouped = {}
        for row in data:
            key = row.get(column, "unknown")
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(row)
        return grouped
    
    async def _aggregate_data(self, data: List[Dict], group_by: str, aggregations: Dict[str, str]) -> List[Dict]:
        """Aggregate data with specified operations"""
        grouped = await self._group_data(data, group_by)
        aggregated = []
        
        for group_key, group_data in grouped.items():
            result = {group_by: group_key}
            
            for column, operation in aggregations.items():
                if operation == "count":
                    result[f"{column}_count"] = len(group_data)
                elif operation == "sum" and self._is_numeric_column(group_data, column):
                    values = [row.get(column, 0) for row in group_data if row.get(column) is not None]
                    result[f"{column}_sum"] = sum(values)
                elif operation == "mean" and self._is_numeric_column(group_data, column):
                    values = [row.get(column, 0) for row in group_data if row.get(column) is not None]
                    result[f"{column}_mean"] = statistics.mean(values) if values else 0
            
            aggregated.append(result)
        
        return aggregated
    
    async def _format_data(self, data: List[Dict], output_format: str) -> Union[str, List[Dict]]:
        """Format data to specified output format"""
        if output_format == "json":
            return json.dumps(data, indent=2)
        elif output_format == "csv":
            if not data:
                return ""
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
            return output.getvalue()
        else:
            return data
    
    async def _apply_transformation(self, data: List[Dict], transformation_type: str, parameters: Dict[str, Any]) -> List[Dict]:
        """Apply data transformation"""
        if transformation_type == "normalize":
            return await self._normalize_data(data, parameters)
        elif transformation_type == "standardize":
            return await self._standardize_data(data, parameters)
        else:
            return data
    
    async def _normalize_data(self, data: List[Dict], parameters: Dict[str, Any]) -> List[Dict]:
        """Normalize numeric columns to 0-1 range"""
        normalized_data = []
        
        for row in data:
            normalized_row = row.copy()
            for column in parameters.get("columns", []):
                if self._is_numeric_column(data, column):
                    values = [r.get(column) for r in data if r.get(column) is not None]
                    if values:
                        min_val = min(values)
                        max_val = max(values)
                        if max_val != min_val:
                            normalized_row[column] = (row.get(column, 0) - min_val) / (max_val - min_val)
            normalized_data.append(normalized_row)
        
        return normalized_data
    
    async def _standardize_data(self, data: List[Dict], parameters: Dict[str, Any]) -> List[Dict]:
        """Standardize numeric columns to z-score"""
        standardized_data = []
        
        for row in data:
            standardized_row = row.copy()
            for column in parameters.get("columns", []):
                if self._is_numeric_column(data, column):
                    values = [r.get(column) for r in data if r.get(column) is not None]
                    if values and len(values) > 1:
                        mean_val = statistics.mean(values)
                        std_val = statistics.stdev(values)
                        if std_val != 0:
                            standardized_row[column] = (row.get(column, 0) - mean_val) / std_val
            standardized_data.append(standardized_row)
        
        return standardized_data
    
    async def _calculate_column_statistics(self, column_data: List[float], statistics_requested: List[str]) -> Dict[str, float]:
        """Calculate statistics for a single column"""
        stats = {}
        
        if "mean" in statistics_requested:
            stats["mean"] = statistics.mean(column_data)
        if "median" in statistics_requested:
            stats["median"] = statistics.median(column_data)
        if "std" in statistics_requested:
            stats["std"] = statistics.stdev(column_data) if len(column_data) > 1 else 0
        if "variance" in statistics_requested:
            stats["variance"] = statistics.variance(column_data) if len(column_data) > 1 else 0
        
        return stats
    
    async def _calculate_overall_statistics(self, data: List[Dict], columns: List[str]) -> Dict[str, Any]:
        """Calculate overall dataset statistics"""
        return {
            "total_records": len(data),
            "total_columns": len(columns),
            "numeric_columns": len([col for col in columns if self._is_numeric_column(data, col)]),
            "text_columns": len([col for col in columns if not self._is_numeric_column(data, col)])
        }
    
    async def _generate_chart_config(self, data: List[Dict], chart_type: str, columns: List[str]) -> Dict[str, Any]:
        """Generate chart configuration"""
        config = {
            "type": chart_type,
            "data": {
                "labels": [],
                "datasets": []
            },
            "options": {
                "responsive": True,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": f"{chart_type.title()} Chart"
                    }
                }
            }
        }
        
        # Generate sample configuration based on chart type
        if chart_type == "bar" and columns:
            config["data"]["labels"] = [str(i) for i in range(min(10, len(data)))]
            config["data"]["datasets"] = [{
                "label": columns[0],
                "data": [row.get(columns[0], 0) for row in data[:10]],
                "backgroundColor": "rgba(54, 162, 235, 0.2)",
                "borderColor": "rgba(54, 162, 235, 1)",
                "borderWidth": 1
            }]
        
        return config


# Export the agent class
__all__ = ["DataAgent"]
