"""Partials and Personas example."""

from rawagents.prompts import PromptManager

def main():
    manager = PromptManager("./examples/prompts/templates")
    
    # Reuse the same template for different personas
    # The template includes shared safety rules automatically
    
    print("--- Persona: Coder ---")
    print(manager.render(
        "04_persona.j2",
        role="Software Engineer",
        instructions="Write clean Python code."
    ))
    
    print("\n--- Persona: Auditor ---")
    print(manager.render(
        "04_persona.j2",
        role="Security Auditor",
        instructions="Check for vulnerabilities."
    ))

if __name__ == "__main__":
    main()

