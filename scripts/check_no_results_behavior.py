from utils.data_loader import get_example_wardrobe
import agent

called = {"suggest": False}

def stub_suggest(*args, **kwargs):
    called["suggest"] = True
    return "SHOULD NOT CALL"

# monkeypatch
agent.suggest_outfit = stub_suggest

session = agent.run_agent("designer ballgown size XXS under $5", get_example_wardrobe())

print("session[\"error\"]:", repr(session.get("error")))
print("session[\"fit_card\"] is None:", session.get("fit_card") is None)
print("suggest_outfit called?:", called["suggest"]) 
