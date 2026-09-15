from pprint import pprint
import agent
from utils.data_loader import get_example_wardrobe

queries = [
    "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers.",
    "designer ballgown size XXS under $5",
]

wardrobe = get_example_wardrobe()

for q in queries:
    print('\n' + '='*40)
    print('Query:', q)
    session = agent.run_agent(q, wardrobe)
    print('\nSESSION DUMP:')
    pprint(session)
    print('\nKeys present:', list(session.keys()))
    print('='*40 + '\n')
