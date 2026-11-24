"""Nombre visible del equipo; los identificadores de vinculación no cambian."""
def number(terminal_id=0):return int(terminal_id or 0)+1

def name(terminal_id=0):return 'PC '+str(number(terminal_id))
