#!/usr/bin/env python3
import asyncio
import websockets
import json
from datetime import datetime
from collections import defaultdict
import statistics

class TimingAnalyzer:
    def __init__(self):
        self.data = []
        self.start_time = None
        self.duration = 60  # 1분
        
    async def collect_data(self):
        uri = "ws://localhost:8001/ws"
        print("="*60)
        print(f"통계 수집 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"수집 시간: {self.duration}초")
        print("="*60)
        
        self.start_time = datetime.now()
        
        try:
            async with websockets.connect(uri) as websocket:
                print("✓ WebSocket 연결 성공\n")
                
                while True:
                    elapsed = (datetime.now() - self.start_time).total_seconds()
                    if elapsed >= self.duration:
                        break
                    
                    remaining = self.duration - elapsed
                    print(f"\r수집 중... 남은 시간: {remaining:.1f}초 | 수집된 메시지: {len(self.data)}개", end='', flush=True)
                    
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=min(remaining + 1, 5)
                        )
                        
                        data = json.loads(message)
                        
                        if data.get('type') == 'robot_update':
                            timing = data['data']['timing']
                            
                            self.data.append({
                                'ai_processing': timing.get('ai_processing', 0),
                                'web_transfer': timing.get('web_transfer', 0),
                                'overhead': timing.get('overhead', 0),
                                'total': timing.get('total', 0),
                                'timestamp': data['data']['received_at']
                            })
                            
                    except asyncio.TimeoutError:
                        continue
                    except KeyError as e:
                        print(f"\n⚠ 필드 오류: {e}")
                        print(f"받은 데이터: {json.dumps(data, indent=2)}")
                        continue
                        
        except Exception as e:
            print(f"\n\n오류 발생: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("\n\n✓ 데이터 수집 완료!\n")
        
        if len(self.data) == 0:
            print("⚠ 수집된 데이터가 없습니다.")
            return
        
        self.analyze()
    
    def analyze(self):
        if not self.data:
            print("⚠ 수집된 데이터가 없습니다.")
            return
        
        # 각 단계별 시간 추출
        ai_times = [d['ai_processing'] for d in self.data]
        web_times = [d['web_transfer'] for d in self.data]
        overhead_times = [d['overhead'] for d in self.data]
        total_times = [d['total'] for d in self.data]
        
        print("="*60)
        print("📊 통계 분석 결과 (수신 시간 기준)")
        print("="*60)
        print(f"총 메시지 수: {len(self.data)}개")
        print(f"수집 기간: {self.duration}초")
        print(f"초당 평균 메시지: {len(self.data) / self.duration:.2f}개/초")
        print()
        
        # 단계별 통계
        stages = [
            ("AI 처리", ai_times),
            ("웹 전송", web_times),
            ("오버헤드", overhead_times),
            ("전체", total_times)
        ]
        
        print("-"*60)
        print(f"{'단계':<15} {'평균':>10} {'최소':>10} {'최대':>10} {'중앙값':>10}")
        print("-"*60)
        
        for stage_name, times in stages:
            if not times or all(t == 0 for t in times):
                print(f"{stage_name:<15} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>10}")
                continue
                
            avg = statistics.mean(times)
            min_val = min(times)
            max_val = max(times)
            median = statistics.median(times)
            
            print(f"{stage_name:<15} {avg:>9.3f}초 {min_val:>9.3f}초 {max_val:>9.3f}초 {median:>9.3f}초")
        
        print("-"*60)
        print()
        
        # 백분위수 분석
        if total_times and not all(t == 0 for t in total_times):
            print("📈 백분위수 분석 (전체 처리 시간)")
            print("-"*60)
            
            percentiles = [50, 75, 90, 95, 99]
            sorted_total = sorted(total_times)
            
            for p in percentiles:
                idx = int(len(sorted_total) * p / 100)
                value = sorted_total[min(idx, len(sorted_total) - 1)]
                print(f"P{p:>2}: {value:.3f}초 ({p}%의 요청이 이 시간 이내 처리)")
            
            print()
        
        # 비율 분석
        avg_ai = statistics.mean(ai_times) if ai_times else 0
        avg_web = statistics.mean(web_times) if web_times else 0
        avg_overhead = statistics.mean(overhead_times) if overhead_times else 0
        avg_total = statistics.mean(total_times) if total_times else 0
        
        if avg_total > 0:
            print("📊 각 단계별 시간 비율")
            print("-"*60)
            
            ai_ratio = (avg_ai / avg_total) * 100
            web_ratio = (avg_web / avg_total) * 100
            overhead_ratio = (avg_overhead / avg_total) * 100
            
            print(f"AI 처리:      {ai_ratio:>6.2f}% ({avg_ai:.3f}초)")
            print(f"웹 전송:      {web_ratio:>6.2f}% ({avg_web:.3f}초)")
            print(f"오버헤드:     {overhead_ratio:>6.2f}% ({avg_overhead:.3f}초)")
            print(f"총합:         100.00% ({avg_total:.3f}초)")
            
            # 검증
            calculated = avg_ai + avg_web + avg_overhead
            diff = abs(calculated - avg_total)
            if diff > 0.001:
                print(f"\n⚠ 경고: 합계 불일치 (차이: {diff:.3f}초)")
            else:
                print(f"\n✓ 합계 검증 통과 (차이: {diff:.6f}초)")
        else:
            print("⚠ 전체 시간이 0초입니다. 데이터를 확인하세요.")
        
        print()
        
        # 표준편차
        print("📉 표준편차 (안정성 지표)")
        print("-"*60)
        for stage_name, times in stages:
            if times and len(times) > 1 and not all(t == 0 for t in times):
                std_dev = statistics.stdev(times)
                print(f"{stage_name:<15} {std_dev:.3f}초")
            else:
                print(f"{stage_name:<15} N/A")
        
        print()
        print("="*60)
        
        # CSV로 저장
        self.save_to_csv()
    
    def save_to_csv(self):
        filename = f"timing_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w') as f:
            f.write("timestamp,ai_processing,web_transfer,overhead,total\n")
            for d in self.data:
                f.write(f"{d['timestamp']},{d['ai_processing']},{d['web_transfer']},{d['overhead']},{d['total']}\n")
        
        print(f"📁 상세 데이터가 {filename}에 저장되었습니다.")
        print()

async def main():
    analyzer = TimingAnalyzer()
    await analyzer.collect_data()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠ 사용자에 의해 중단되었습니다.")