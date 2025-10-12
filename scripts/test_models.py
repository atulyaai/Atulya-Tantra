"""
Model Speed & Quality Test
Compare different Ollama models for Atulya Tantra
"""

import ollama
import time
import sys

def test_model(model_name: str, prompt: str) -> dict:
    """Test a model's response time and quality"""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}")
    
    try:
        start_time = time.time()
        
        response = ollama.chat(
            model=model_name,
            messages=[
                {'role': 'system', 'content': 'You are a helpful AI. Keep responses under 2 sentences.'},
                {'role': 'user', 'content': prompt}
            ],
            options={
                'num_predict': 30,
                'temperature': 0.8,
                'num_ctx': 512,
            }
        )
        
        elapsed = time.time() - start_time
        content = response['message']['content'].strip()
        
        print(f"✅ Response time: {elapsed:.2f}s")
        print(f"📝 Response: {content}")
        print(f"📊 Length: {len(content)} chars, {len(content.split())} words")
        
        return {
            'model': model_name,
            'time': elapsed,
            'response': content,
            'success': True
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return {
            'model': model_name,
            'time': 0,
            'response': '',
            'success': False,
            'error': str(e)
        }

def main():
    """Test all available models"""
    print("🚀 Atulya Tantra - Model Performance Test")
    print("Testing models for speed and quality...\n")
    
    # Test prompts
    test_cases = [
        ("Greeting", "Hello, how are you?"),
        ("Simple", "What's 2+2?"),
        ("Complex", "Explain quantum entanglement simply."),
    ]
    
    # Models to test
    models = ['gemma2:2b', 'phi3:mini', 'mistral:7b-instruct-v0.3-q4_0']
    
    results = {}
    
    for test_name, prompt in test_cases:
        print(f"\n\n{'#'*60}")
        print(f"TEST CASE: {test_name}")
        print(f"Prompt: {prompt}")
        print(f"{'#'*60}")
        
        results[test_name] = []
        
        for model in models:
            result = test_model(model, prompt)
            results[test_name].append(result)
            time.sleep(1)
    
    # Summary
    print("\n\n" + "="*60)
    print("📊 SUMMARY - Average Response Times")
    print("="*60)
    
    for model in models:
        times = []
        for test_name in results:
            for result in results[test_name]:
                if result['model'] == model and result['success']:
                    times.append(result['time'])
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"{model:40s} {avg_time:6.2f}s")
        else:
            print(f"{model:40s} NOT AVAILABLE")
    
    print("\n" + "="*60)
    print("🏆 RECOMMENDATION")
    print("="*60)
    print("For voice conversations: gemma2:2b (fastest)")
    print("For complex tasks: mistral:7b (best quality)")
    print("For balance: phi3:mini (good mix)")

if __name__ == "__main__":
    main()

