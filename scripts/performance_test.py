#!/usr/bin/env python3
"""
This script tests the performance improvements in FleDjSON.
It compares the standard tree rendering with the optimized tree rendering.
"""
import sys
import time
import json
import os
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary modules
from src.optimizations import TreeOptimizer
from src.managers.ui_manager import UIManager

# Mock app_state and ui_controls for testing
app_state = {
    "expanded_nodes": set(),
    "data_map": {},
    "children_map": {},
    "root_ids": []
}

ui_controls = {
    "tree_view": None
}

def generate_test_data(num_nodes=1000, max_depth=5):
    """Generate test data with a specified number of nodes and maximum depth."""
    data = []
    id_counter = 1
    
    def create_node(parent_id=None, current_depth=0):
        nonlocal id_counter
        node_id = f"node_{id_counter}"
        id_counter += 1
        
        node = {
            "id": node_id,
            "name": f"Node {node_id}",
            "depth": current_depth,
            "description": f"Test node at depth {current_depth}"
        }
        
        if parent_id:
            node["parent"] = parent_id
            
        children = []
        if current_depth < max_depth and id_counter <= num_nodes:
            # Create 1-5 children for this node
            num_children = min(random.randint(1, 5), num_nodes - id_counter + 1)
            for _ in range(num_children):
                if id_counter > num_nodes:
                    break
                child_id = f"node_{id_counter}"
                children.append(child_id)
                data.append(create_node(node_id, current_depth + 1))
                
        if children:
            node["children"] = children
            
        return node
    
    # Create root nodes (level 0)
    num_roots = min(5, num_nodes)
    for _ in range(num_roots):
        data.append(create_node(None, 0))
        
    return data

def build_data_maps(data):
    """Build data_map, children_map, and root_ids from the data."""
    data_map = {}
    children_map = {}
    root_ids = []
    
    for item in data:
        item_id = item["id"]
        data_map[item_id] = item
        
        if "children" in item and item["children"]:
            children_map[item_id] = item["children"]
            
        if "depth" in item and item["depth"] == 0:
            root_ids.append(item_id)
            
    return data_map, children_map, root_ids

def test_standard_tree_rendering(ui_manager, iterations=5):
    """Test the standard tree rendering performance."""
    start_time = time.time()
    
    for _ in range(iterations):
        # Call the standard build_list_tiles method
        tiles = ui_manager.build_list_tiles(app_state["root_ids"], depth=0)
        
    end_time = time.time()
    avg_time = (end_time - start_time) / iterations
    
    return avg_time, len(tiles)

def test_optimized_tree_rendering(ui_manager, tree_optimizer, iterations=5):
    """Test the optimized tree rendering performance."""
    start_time = time.time()
    
    for _ in range(iterations):
        # Set viewport to show a reasonable number of nodes
        tree_optimizer.set_viewport(0, 100)
        
        # Get the nodes in the viewport
        viewport_nodes = tree_optimizer.get_viewport_nodes()
        
        # Build optimized tiles
        tiles = ui_manager._build_optimized_list_tiles(viewport_nodes, tree_optimizer)
        
    end_time = time.time()
    avg_time = (end_time - start_time) / iterations
    
    return avg_time, len(tiles)

def main():
    """Main test function."""
    global app_state
    
    print("FleDjSON Performance Test")
    print("=" * 40)
    
    # Generate test data
    node_counts = [100, 500, 1000]
    
    for count in node_counts:
        print(f"\nTesting with {count} nodes:")
        
        # Generate test data
        data = generate_test_data(count)
        
        # Build data maps
        data_map, children_map, root_ids = build_data_maps(data)
        
        # Update app_state
        app_state["data_map"] = data_map
        app_state["children_map"] = children_map
        app_state["root_ids"] = root_ids
        
        # Create UI manager
        ui_manager = UIManager(app_state, ui_controls)
        
        # Test standard rendering
        std_time, std_tiles = test_standard_tree_rendering(ui_manager)
        print(f"  Standard rendering: {std_time:.4f} seconds (generated {std_tiles} tiles)")
        
        # Create tree optimizer
        tree_optimizer = TreeOptimizer(ui_controls, app_state)
        tree_optimizer.initialize(root_ids, data_map)
        
        # Test optimized rendering
        opt_time, opt_tiles = test_optimized_tree_rendering(ui_manager, tree_optimizer)
        print(f"  Optimized rendering: {opt_time:.4f} seconds (generated {opt_tiles} tiles)")
        
        # Calculate improvement
        improvement = (std_time - opt_time) / std_time * 100
        print(f"  Performance improvement: {improvement:.1f}%")
        print(f"  Memory efficiency: {opt_tiles} vs {std_tiles} tiles ({(1 - opt_tiles/std_tiles) * 100:.1f}% reduction)")
        
    print("\nPerformance test completed")

if __name__ == "__main__":
    main()