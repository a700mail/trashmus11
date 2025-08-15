#!/usr/bin/env python3
"""
Скрипт для тестирования производительности оптимизированного Telegram Music Bot
"""

import asyncio
import time
import requests
import json
import statistics
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PerformanceTester:
    """Класс для тестирования производительности бота"""
    
    def __init__(self, base_url: str = "http://localhost:10000"):
        self.base_url = base_url
        self.results = {}
        self.test_data = {
            "webhook_payload": {
                "update_id": 123456789,
                "message": {
                    "message_id": 1,
                    "from": {"id": 123456, "first_name": "TestUser"},
                    "chat": {"id": 123456, "type": "private"},
                    "date": int(time.time()),
                    "text": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                }
            }
        }
    
    def test_endpoint_response_time(self, endpoint: str, method: str = "GET", 
                                  data: dict = None, iterations: int = 10) -> Dict:
        """Тестирует время отклика endpoint"""
        logger.info(f"Тестируем {method} {endpoint} ({iterations} итераций)")
        
        response_times = []
        status_codes = []
        errors = []
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                elif method == "POST":
                    response = requests.post(f"{self.base_url}{endpoint}", 
                                          json=data, timeout=30)
                
                end_time = time.time()
                response_time = end_time - start_time
                
                response_times.append(response_time)
                status_codes.append(response.status_code)
                
                logger.info(f"Итерация {i+1}: {response_time:.3f}s, статус: {response.status_code}")
                
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Ошибка в итерации {i+1}: {e}")
        
        # Анализ результатов
        if response_times:
            result = {
                "endpoint": endpoint,
                "method": method,
                "iterations": iterations,
                "successful_requests": len(response_times),
                "failed_requests": len(errors),
                "response_times": {
                    "min": min(response_times),
                    "max": max(response_times),
                    "mean": statistics.mean(response_times),
                    "median": statistics.median(response_times),
                    "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
                },
                "status_codes": status_codes,
                "errors": errors
            }
        else:
            result = {
                "endpoint": endpoint,
                "method": method,
                "iterations": iterations,
                "successful_requests": 0,
                "failed_requests": len(errors),
                "errors": errors
            }
        
        self.results[endpoint] = result
        return result
    
    def test_concurrent_requests(self, endpoint: str, concurrent_users: int = 10, 
                                total_requests: int = 100) -> Dict:
        """Тестирует производительность при одновременных запросах"""
        logger.info(f"Тестируем {endpoint} с {concurrent_users} одновременными пользователями")
        
        def make_request():
            try:
                start_time = time.time()
                response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                end_time = time.time()
                return {
                    "status_code": response.status_code,
                    "response_time": end_time - start_time,
                    "success": response.status_code == 200
                }
            except Exception as e:
                return {
                    "status_code": 0,
                    "response_time": 0,
                    "success": False,
                    "error": str(e)
                }
        
        # Выполняем запросы в пуле потоков
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(make_request) for _ in range(total_requests)]
            results = [future.result() for future in futures]
        
        # Анализируем результаты
        successful_requests = [r for r in results if r["success"]]
        failed_requests = [r for r in results if not r["success"]]
        
        if successful_requests:
            response_times = [r["response_time"] for r in successful_requests]
            result = {
                "endpoint": endpoint,
                "concurrent_users": concurrent_users,
                "total_requests": total_requests,
                "successful_requests": len(successful_requests),
                "failed_requests": len(failed_requests),
                "success_rate": len(successful_requests) / total_requests * 100,
                "response_times": {
                    "min": min(response_times),
                    "max": max(response_times),
                    "mean": statistics.mean(response_times),
                    "median": statistics.median(response_times),
                    "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
                },
                "throughput": len(successful_requests) / max(response_times) if response_times else 0
            }
        else:
            result = {
                "endpoint": endpoint,
                "concurrent_users": concurrent_users,
                "total_requests": total_requests,
                "successful_requests": 0,
                "failed_requests": len(failed_requests),
                "success_rate": 0,
                "errors": [r.get("error", "Unknown error") for r in failed_requests]
            }
        
        self.results[f"{endpoint}_concurrent"] = result
        return result
    
    def test_webhook_performance(self, iterations: int = 50) -> Dict:
        """Тестирует производительность webhook endpoint"""
        logger.info(f"Тестируем webhook производительность ({iterations} итераций)")
        
        response_times = []
        status_codes = []
        errors = []
        
        for i in range(iterations):
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.base_url}/webhook",
                    json=self.test_data["webhook_payload"],
                    timeout=30
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                
                response_times.append(response_time)
                status_codes.append(response.status_code)
                
                if i % 10 == 0:
                    logger.info(f"Webhook итерация {i+1}: {response_time:.3f}s, статус: {response.status_code}")
                
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Ошибка webhook в итерации {i+1}: {e}")
        
        # Анализ результатов
        if response_times:
            result = {
                "test_type": "webhook_performance",
                "iterations": iterations,
                "successful_requests": len(response_times),
                "failed_requests": len(errors),
                "response_times": {
                    "min": min(response_times),
                    "max": max(response_times),
                    "mean": statistics.mean(response_times),
                    "median": statistics.median(response_times),
                    "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
                },
                "status_codes": status_codes,
                "errors": errors,
                "throughput": len(response_times) / max(response_times) if response_times else 0
            }
        else:
            result = {
                "test_type": "webhook_performance",
                "iterations": iterations,
                "successful_requests": 0,
                "failed_requests": len(errors),
                "errors": errors
            }
        
        self.results["webhook_performance"] = result
        return result
    
    def test_cache_efficiency(self) -> Dict:
        """Тестирует эффективность кэширования"""
        logger.info("Тестируем эффективность кэширования")
        
        # Первый запрос (без кэша)
        start_time = time.time()
        response1 = requests.get(f"{self.base_url}/health", timeout=30)
        first_request_time = time.time() - start_time
        
        # Второй запрос (с кэшем)
        start_time = time.time()
        response2 = requests.get(f"{self.base_url}/health", timeout=30)
        second_request_time = time.time() - start_time
        
        # Третий запрос (с кэшем)
        start_time = time.time()
        response3 = requests.get(f"{self.base_url}/health", timeout=30)
        third_request_time = time.time() - start_time
        
        cache_efficiency = {
            "first_request_time": first_request_time,
            "second_request_time": second_request_time,
            "third_request_time": third_request_time,
            "cache_speedup": first_request_time / second_request_time if second_request_time > 0 else 0,
            "average_cached_time": (second_request_time + third_request_time) / 2,
            "cache_benefit": (first_request_time - (second_request_time + third_request_time) / 2) / first_request_time * 100 if first_request_time > 0 else 0
        }
        
        self.results["cache_efficiency"] = cache_efficiency
        return cache_efficiency
    
    def run_full_test_suite(self) -> Dict:
        """Запускает полный набор тестов"""
        logger.info("🚀 Запуск полного набора тестов производительности")
        
        start_time = time.time()
        
        # Тестируем основные endpoints
        self.test_endpoint_response_time("/", "GET", iterations=20)
        self.test_endpoint_response_time("/health", "GET", iterations=20)
        self.test_endpoint_response_time("/bot_status", "GET", iterations=20)
        
        # Тестируем webhook
        self.test_webhook_performance(iterations=30)
        
        # Тестируем конкурентные запросы
        self.test_concurrent_requests("/health", concurrent_users=5, total_requests=50)
        self.test_concurrent_requests("/", concurrent_users=3, total_requests=30)
        
        # Тестируем кэширование
        self.test_cache_efficiency()
        
        total_time = time.time() - start_time
        
        # Сводный отчет
        summary = {
            "test_duration": total_time,
            "total_tests": len(self.results),
            "results": self.results,
            "performance_score": self._calculate_performance_score()
        }
        
        self.results["summary"] = summary
        return summary
    
    def _calculate_performance_score(self) -> float:
        """Вычисляет общий балл производительности"""
        if not self.results:
            return 0.0
        
        scores = []
        
        for test_name, result in self.results.items():
            if "response_times" in result:
                # Оцениваем время отклика (меньше = лучше)
                mean_time = result["response_times"]["mean"]
                if mean_time < 0.1:
                    scores.append(100)
                elif mean_time < 0.5:
                    scores.append(90)
                elif mean_time < 1.0:
                    scores.append(80)
                elif mean_time < 2.0:
                    scores.append(70)
                elif mean_time < 5.0:
                    scores.append(60)
                else:
                    scores.append(50)
            
            if "success_rate" in result:
                # Оцениваем успешность запросов
                success_rate = result["success_rate"]
                scores.append(success_rate)
            
            if "cache_benefit" in result:
                # Оцениваем эффективность кэша
                cache_benefit = result["cache_benefit"]
                if cache_benefit > 50:
                    scores.append(100)
                elif cache_benefit > 30:
                    scores.append(80)
                elif cache_benefit > 10:
                    scores.append(60)
                else:
                    scores.append(40)
        
        return statistics.mean(scores) if scores else 0.0
    
    def print_results(self):
        """Выводит результаты тестирования"""
        print("\n" + "="*80)
        print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ ПРОИЗВОДИТЕЛЬНОСТИ")
        print("="*80)
        
        if "summary" in self.results:
            summary = self.results["summary"]
            print(f"\n🎯 Общий балл производительности: {summary['performance_score']:.1f}/100")
            print(f"⏱️  Общее время тестирования: {summary['test_duration']:.2f} секунд")
            print(f"🧪 Количество тестов: {summary['total_tests']}")
        
        print("\n📈 Детальные результаты:")
        print("-" * 80)
        
        for test_name, result in self.results.items():
            if test_name == "summary":
                continue
                
            print(f"\n🔍 {test_name.upper()}")
            
            if "response_times" in result:
                rt = result["response_times"]
                print(f"   ⏱️  Время отклика:")
                print(f"      Минимум: {rt['min']:.3f}s")
                print(f"      Максимум: {rt['max']:.3f}s")
                print(f"      Среднее: {rt['mean']:.3f}s")
                print(f"      Медиана: {rt['median']:.3f}s")
                print(f"      Стандартное отклонение: {rt['std_dev']:.3f}s")
            
            if "success_rate" in result:
                print(f"   ✅ Успешность: {result['success_rate']:.1f}%")
            
            if "throughput" in result:
                print(f"   🚀 Пропускная способность: {result['throughput']:.2f} req/s")
            
            if "cache_benefit" in result:
                print(f"   💾 Эффективность кэша: {result['cache_benefit']:.1f}%")
            
            if "errors" in result and result["errors"]:
                print(f"   ❌ Ошибки: {len(result['errors'])}")
                for error in result["errors"][:3]:  # Показываем первые 3 ошибки
                    print(f"      - {error}")
    
    def save_results(self, filename: str = "performance_test_results.json"):
        """Сохраняет результаты в JSON файл"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Результаты сохранены в {filename}")
        except Exception as e:
            logger.error(f"Ошибка сохранения результатов: {e}")

def main():
    """Главная функция"""
    print("🚀 Тестирование производительности Telegram Music Bot")
    print("=" * 60)
    
    # Проверяем доступность бота
    try:
        response = requests.get("http://localhost:10000/health", timeout=10)
        if response.status_code == 200:
            print("✅ Бот доступен для тестирования")
        else:
            print(f"⚠️  Бот отвечает со статусом: {response.status_code}")
    except Exception as e:
        print(f"❌ Бот недоступен: {e}")
        print("Убедитесь, что бот запущен на http://localhost:10000")
        return
    
    # Создаем тестер и запускаем тесты
    tester = PerformanceTester()
    
    try:
        # Запускаем полный набор тестов
        results = tester.run_full_test_suite()
        
        # Выводим результаты
        tester.print_results()
        
        # Сохраняем результаты
        tester.save_results()
        
        # Рекомендации
        print("\n" + "="*80)
        print("💡 РЕКОМЕНДАЦИИ ПО ОПТИМИЗАЦИИ")
        print("="*80)
        
        if "summary" in results:
            score = results["summary"]["performance_score"]
            
            if score >= 90:
                print("🎉 Отличная производительность! Бот работает оптимально.")
            elif score >= 80:
                print("👍 Хорошая производительность. Незначительные улучшения возможны.")
            elif score >= 70:
                print("⚠️  Средняя производительность. Рекомендуются оптимизации.")
            elif score >= 60:
                print("🔧 Низкая производительность. Требуются значительные улучшения.")
            else:
                print("❌ Критически низкая производительность. Необходима полная оптимизация.")
        
        print("\n📚 Для улучшения производительности изучите OPTIMIZATION_GUIDE.md")
        
    except KeyboardInterrupt:
        print("\n⏹️  Тестирование прервано пользователем")
    except Exception as e:
        logger.error(f"Ошибка во время тестирования: {e}")
        print(f"\n❌ Произошла ошибка: {e}")

if __name__ == "__main__":
    main()
