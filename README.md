# Tranquil Tempest
### The ISMCTS-based Mighty AI

Tranquil Tempest consists of two main modules: **tranquil** and **tempest**.

The first module, `tranquil.py`, is the interface module of the AI, meant to be accessed by 
the game server of Mighty-Online in an API-like manner. It handles AI move requests, and
distributes them to the second module, described below.

The second module, `tempest.py`, is the actual working AI behind Tranquil Tempest.

#### Task list:
- [ ] Create game logic
- [ ] Implement ISMCTS
- [ ] Implement `tranquil.py`
