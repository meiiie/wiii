"""
Quick test to verify GuardianAgent uses the current Google runtime default.
"""
import sys
sys.path.insert(0, ".")

from app.engine.guardian_agent import GuardianAgent, GuardianConfig

def test_model():
    print("=" * 60)
    print("GUARDIAN AGENT MODEL VERIFICATION")
    print("=" * 60)
    
    # Create agent
    config = GuardianConfig(enable_llm=True)
    agent = GuardianAgent(config=config)
    
    # Check model
    if agent._llm:
        model_name = agent._llm.model
        print(f"✅ LLM initialized with model: {model_name}")
        
        if "gemini-3.1-flash-lite-preview" in model_name:
            print("✅ Correct model: gemini-3.1-flash-lite-preview")
            return True
        else:
            print(f"❌ Wrong model! Expected gemini-3.1-flash-lite-preview, got {model_name}")
            return False
    else:
        print("❌ LLM not initialized")
        return False

if __name__ == "__main__":
    success = test_model()
    sys.exit(0 if success else 1)
