from src.search_manager import SearchManager
import json

print('Checking search functionality')
print('Recreating app_state...')
app_state = {'raw_data': [], 'data_map': {}, 'root_ids': []}
app_state['raw_data'] = [
    {
        'id': '1', 
        'profile': {
            'name': 'alice', 
            'contact': {
                'email': 'alice@example.com', 
                'phone': '123-456-7890'
            }
        }, 
        'tags': ['a', 'b']
    },
    {
        'id': '2', 
        'profile': {
            'name': 'bob', 
            'contact': {
                'email': 'boby@example.com', 
                'phone': '145656'
            }
        }, 
        'tags': ['a', 'b']
    },
    {
        'id': '3', 
        'profile': {
            'name': '俺', 
            'contact': {
                'email': 'ore@dev.it', 
                'phone': '000-0000-0000'
            }
        }, 
        'tags': ['him', 'and', 'them']
    }
]

print(f'Raw data: {len(app_state["raw_data"])} items')
app_state['id_key'] = 'id'
app_state['children_key'] = 'tags'
app_state['label_key'] = 'id'

print('Creating search manager...')
search_manager = SearchManager(app_state, {})

print('Building search index...')
search_manager.build_search_index()
print(f'Search index size: {len(search_manager.search_index)} nodes')

print('Search results for "dev":')
search_manager.search_term = 'dev'
search_manager.perform_search()
print(f'Results count: {len(search_manager.search_results)}')
for result in search_manager.search_results:
    print(f'- ID: {result["id"]}, preview: {result["text"][:100]}...')