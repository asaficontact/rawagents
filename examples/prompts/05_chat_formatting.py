"""Chat Formatting and CoT example."""

from rawagents.prompts import PromptManager

def main():
    manager = PromptManager("./examples/prompts/templates")
    
    # Simulate a Chain-of-Thought reasoning process
    steps = [
        "1. Analyze user intent.",
        "2. Identify key constraints.",
        "3. Formulate response."
    ]
    
    # Render a structured chat transcript or reasoning block
    prompt = manager.render(
        "05_chat.j2",
        query="Why is the sky blue?",
        reasoning_steps="\n".join(steps),
        answer="Rayleigh scattering."
    )
    
    print("--- CoT Prompt ---")
    print(prompt)

if __name__ == "__main__":
    main()

