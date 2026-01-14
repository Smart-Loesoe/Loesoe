"""
Bandit-algoritmes voor adaptieve keuzes.
Later vullen we dit met o.a. epsilon-greedy, UCB, Thompson sampling.
"""

def select_action(options):
    """
    Kies een actie uit de lijst met opties.
    Voor nu: geef gewoon de eerste terug.
    """
    return options[0] if options else None
