from pprint import pprint
import agent
from utils.data_loader import get_example_wardrobe

captured = {'suggest_items': [], 'create_calls': []}

orig_suggest = agent.suggest_outfit
orig_create = agent.create_fit_card


def wrapper_suggest(item, wardrobe):
    captured['suggest_items'].append(item)
    return orig_suggest(item, wardrobe)


def wrapper_create(outfit, item):
    captured['create_calls'].append({'outfit': outfit, 'item': item})
    return orig_create(outfit, item)

agent.suggest_outfit = wrapper_suggest
agent.create_fit_card = wrapper_create

query = "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"
wardrobe = get_example_wardrobe()

print('\nRunning run_agent with demo query (capturing all calls)...')
session = agent.run_agent(query, wardrobe)

print('\nSESSION selected_item:')
pprint(session.get('selected_item'))
print('id(selected_item)=', id(session.get('selected_item')))

print('\nAll suggest_outfit calls (in order):')
for i, it in enumerate(captured['suggest_items']):
    print(f"call {i}: id={id(it)} id==selected? {id(it)==id(session.get('selected_item'))}")
    pprint(it)

print('\nSESSION outfit_suggestion:')
print(session.get('outfit_suggestion'))

print('\nAll create_fit_card calls (in order):')
for i, call in enumerate(captured['create_calls']):
    print(f"call {i}: outfit equals session['outfit_suggestion']? {call['outfit']==session.get('outfit_suggestion')}")
    print('item id==selected?', id(call['item'])==id(session.get('selected_item')))
    pprint(call)

# restore
agent.suggest_outfit = orig_suggest
agent.create_fit_card = orig_create

print('\nDone.')
