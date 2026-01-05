"""Logic and Control Flow example."""

from rawagents.prompts import PromptManager

def main():
    manager = PromptManager("./examples/prompts/templates")
    
    items = [f"Log entry #{i}" for i in range(1, 10)]
    
    # Scenario 1: Normal mode
    print("--- Normal Mode ---")
    print(manager.render(
        "02_logic.j2",
        items=items[:3],
        strict_mode=False
    ))
    
    # Scenario 2: Strict mode with many items (triggers loop logic)
    print("\n--- Strict Mode + Truncation Logic ---")
    print(manager.render(
        "02_logic.j2",
        items=items,
        strict_mode=True
    ))

if __name__ == "__main__":
    main()

