from pprint import pprint
import agent
from utils.data_loader import get_example_wardrobe

captured = {}

orig_suggest = agent.suggest_outfit
orig_create = agent.create_fit_card


def wrapper_suggest(item, wardrobe):
    # record the exact object (identity) and a shallow copy for visibility
    captured['suggest_item'] = item
    try:
        return orig_suggest(item, wardrobe)
    except Exception as e:
        captured['suggest_error'] = str(e)
        raise


def wrapper_create(outfit, item):
    captured['create_outfit'] = outfit
    captured['create_item'] = item
    try:
        return orig_create(outfit, item)
    except Exception as e:
        captured['create_error'] = str(e)
        raise

# Monkeypatch the agent-level references
agent.suggest_outfit = wrapper_suggest
agent.create_fit_card = wrapper_create

query = "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"
wardrobe = get_example_wardrobe()

print('\nRunning run_agent with demo query...')
session = agent.run_agent(query, wardrobe)

print('\nSESSION SELECTED ITEM:')
pprint(session.get('selected_item'))
print('id(session[selected_item]) =', id(session.get('selected_item')))

print('\nCAPTURED suggest_outfit ITEM:')
pprint(captured.get('suggest_item'))
print("id(captured['suggest_item']) =", id(captured.get('suggest_item')))

same_obj = id(session.get('selected_item')) == id(captured.get('suggest_item'))
print('\nDict identity equal (selected_item passed to suggest_outfit?):', same_obj)

print('\nSESSION outfit_suggestion:')
print(session.get('outfit_suggestion'))

print('\nCAPTURED create_fit_card outfit argument:')
print(captured.get('create_outfit'))

print('\nOutfit strings equal (session vs passed to create_fit_card?):', session.get('outfit_suggestion') == captured.get('create_outfit'))

print('\nCAPTURED create_fit_card item argument (should equal selected_item):')
pprint(captured.get('create_item'))
print('id(captured[create_item]) =', id(captured.get('create_item')))
print('selected_item id again =', id(session.get('selected_item')))
print('create_item identity equal to selected_item?:', id(captured.get('create_item')) == id(session.get('selected_item')))

# Restore originals (cleanup)
agent.suggest_outfit = orig_suggest
agent.create_fit_card = orig_create

print('\nDone.')
