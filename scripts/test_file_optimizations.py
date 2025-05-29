#!/usr/bin/env python3
"""
Utility script to test optimizations on a specific JSON file.
This script helps users evaluate performance improvements when working with large JSON files.
"""
import sys
import os
import time
import json
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import optimization utilities
try:
    from src.optimizations import LazyJSONLoader, performance_log
except ImportError:
    print("Error: Could not import optimization modules.")
    print("Make sure you're running this script from the FleDjSON directory.")
    sys.exit(1)

@performance_log(label="Standard JSON Loading")
def load_json_standard(file_path):
    """Load JSON file using standard json.load"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

@performance_log(label="Optimized JSON Loading")
def load_json_optimized(file_path):
    """Load JSON file using LazyJSONLoader"""
    loader = LazyJSONLoader(file_path)
    structure = loader.get_structure()
    
    # Only load full data if structure was successfully analyzed
    if structure and "error" not in structure:
        return loader.load_full()
    else:
        print(f"Error analyzing file structure: {structure.get('error', 'Unknown error')}")
        return None

def analyze_json_structure(data):
    """Perform basic analysis on JSON structure"""
    result = {
        "total_items": 0,
        "max_depth": 0,
        "array_items": 0,
        "object_items": 0,
        "primitive_items": 0,
        "estimated_memory": 0
    }
    
    def analyze_item(item, depth=0):
        """Recursively analyze an item"""
        nonlocal result
        result["total_items"] += 1
        result["max_depth"] = max(result["max_depth"], depth)
        
        # Estimate memory usage
        result["estimated_memory"] += sys.getsizeof(item)
        
        if isinstance(item, dict):
            result["object_items"] += 1
            for key, value in item.items():
                result["estimated_memory"] += sys.getsizeof(key)
                analyze_item(value, depth + 1)
        elif isinstance(item, list):
            result["array_items"] += 1
            for value in item:
                analyze_item(value, depth + 1)
        else:
            result["primitive_items"] += 1
    
    # Start analysis
    if isinstance(data, list):
        for item in data:
            analyze_item(item)
    else:
        analyze_item(data)
    
    return result

def main():
    """Main function"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test optimizations on a JSON file')
    parser.add_argument('file_path', help='Path to the JSON file to test')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze file structure, do not load data')
    args = parser.parse_args()
    
    file_path = args.file_path
    
    # Check if file exists
    if not os.path.isfile(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)
    
    # Check file size
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"File: {os.path.basename(file_path)}")
    print(f"Size: {file_size_mb:.2f} MB")
    
    # Create LazyJSONLoader for structure analysis
    loader = LazyJSONLoader(file_path)
    structure = loader.get_structure()
    
    print("\nFile Structure Analysis:")
    print(f"  Type: {structure.get('type', 'unknown')}")
    if structure.get("estimated_items"):
        print(f"  Estimated items: {structure.get('estimated_items')}")
    
    # If file is very large, warn user
    if file_size_mb > 50:
        print("\nWarning: This file is quite large. Loading it may take a while.")
        if not args.analyze_only:
            response = input("Do you want to proceed with loading the entire file? (y/n): ")
            if response.lower() != 'y':
                args.analyze_only = True
    
    if args.analyze_only:
        print("\nSkipping data loading as requested.")
        sys.exit(0)
    
    print("\nPerformance Test:")
    print("=" * 40)
    
    # Load with standard method
    start_time = time.time()
    try:
        standard_data = load_json_standard(file_path)
        standard_time = time.time() - start_time
        print(f"Standard loading completed in {standard_time:.4f} seconds")
    except Exception as e:
        print(f"Error loading with standard method: {e}")
        standard_data = None
    
    # Load with optimized method
    start_time = time.time()
    try:
        optimized_data = load_json_optimized(file_path)
        optimized_time = time.time() - start_time
        print(f"Optimized loading completed in {optimized_time:.4f} seconds")
    except Exception as e:
        print(f"Error loading with optimized method: {e}")
        optimized_data = None
    
    # Compare results if both methods succeeded
    if standard_data is not None and optimized_data is not None:
        # Calculate improvement
        if standard_time > 0:
            improvement = (standard_time - optimized_time) / standard_time * 100
            print(f"\nPerformance improvement: {improvement:.1f}%")
        
        # Analyze data structure
        print("\nData Analysis:")
        print("=" * 40)
        analysis = analyze_json_structure(standard_data)
        
        print(f"Total items: {analysis['total_items']}")
        print(f"Maximum depth: {analysis['max_depth']}")
        print(f"Array items: {analysis['array_items']}")
        print(f"Object items: {analysis['object_items']}")
        print(f"Primitive items: {analysis['primitive_items']}")
        print(f"Estimated memory usage: {analysis['estimated_memory'] / (1024 * 1024):.2f} MB")
        
        # Recommend optimization settings
        print("\nRecommendations:")
        print("=" * 40)
        
        if analysis['total_items'] > 1000 or file_size_mb > 10:
            print("[OK] Use LazyJSONLoader for large file loading")
            print("[OK] Enable tree optimization with TreeOptimizer")
            print("[OK] Use background processing for operations")
        else:
            print("[INFO] Standard loading is sufficient for this file size")
            
        if analysis['max_depth'] > 5 or analysis['object_items'] > 500:
            print("[OK] Enable tree node expansion/collapse optimizations")
        
        if analysis['array_items'] > 100:
            print("[OK] Use lazy loading for large array items")

if __name__ == "__main__":
    main()