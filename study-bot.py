import os
import sys
from dotenv import load_dotenv  # .env 파일에서 토큰 가져오지
import discord
from discord.ext import commands, tasks
import asyncio
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta, time
import pytz
import signal
import psycopg2  # Heroku Postgres 연결
from psycopg2 import Error  
from apscheduler.schedulers.asyncio import AsyncIOScheduler # 실제 시간에 따른 작업 스케줄러


# .env 파일애서 토큰 가져오기
load_dotenv()

# Heroku 환경 변수에서 토큰 가져오기
token = os.getenv('TOKEN')
database_url = os.getenv('DATABASE_URL')


# intent를 추가하여 봇이 서버의 특정 이벤트를 구독하도록 허용
intents = discord.Intents.default()
intents.messages = True  # 메시지를 읽고 반응하도록
intents.message_content = True  # 메시지 내용에 접근
intents.guilds = True  # 채널
intents.voice_states = True #음성 상태 정보 갱신
intents.members = True  # 멤버 관련 이벤트 처리 활성화
intents.presences = True  # 멤버의 상태 변화 감지 활성화
intents.reactions = True  # 반응 관련 이벤트 처리 활성화

# 봇 클라이언트 설정
client = discord.Client(intents = intents)



# ---------------------------------------- 데이터베이스 연결 설정 ----------------------------------------
    
# PostgreSQL 데이터베이스 연결 설정 -- 기존 mariaDB에서 PostgreSQL로 변경
def create_db_connection():
    try:
        connection = psycopg2.connect(os.getenv('DATABASE_URL'))
        return connection
    except Exception as e:
        print(f"Error: '{e}'")
        return None
    

# ---------------------------------------- 이틀이 지난 공부 세션 정보는 DB에서 삭제 ----------------------------------------

# 이틀이 지난 데이터를 삭제하는 함수 (이틀이 지나면 그 다음 0시에 삭제됨)
# def delete_old_sessions():
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # 이틀 전 날짜 계산
            two_days_ago = (datetime.now(pytz.timezone('Asia/Seoul')) - timedelta(days=2)).strftime('%Y-%m-%d')
            cursor.execute(
                "DELETE FROM study_session WHERE session_start_time < %s",
                (two_days_ago,)
            )
            connection.commit()
            print(f"{two_days_ago} 이전의 데이터를 삭제했습니다.")
        except Error as e:
            print(f"에러 발생: '{e}'")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")


# ---------------------------------------- 스케줄러 ----------------------------------------

# 스케줄러 설정 :: 실제 한국 시간에 따라 일간/주간 공부순위 안내하는 함수 예약 시 사용
scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
# scheduler.add_job(delete_old_sessions, 'cron', hour=0, minute=0)


# 자정에 end_study_session_at_midnight 함수 예약
@scheduler.scheduled_job('cron', hour=0, minute=0, timezone='Asia/Seoul')
async def schedule_midnight_tasks():
    print("자정 재부팅 시작. 안전하게 종료 중...")
    await end_study_session_at_midnight()


# 매일 0시에 결석 체크
@scheduler.scheduled_job('cron', hour=0, minute=0, timezone='Asia/Seoul')
async def check_absences():
    print("check_absences 함수 시작")
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            print("데이터베이스 연결 성공")
            # 휴가 또는 출석한 멤버를 제외한 나머지 멤버 찾기
            cursor.execute("""
                SELECT m.member_id, m.member_nickname
                FROM member m
                JOIN membership_period mp ON m.member_id = mp.member_id
                LEFT JOIN vacation_log v ON m.member_id = v.member_id AND v.vacation_date = CURRENT_DATE - INTERVAL '1 day'
                LEFT JOIN activity_log a ON m.member_id = a.member_id AND a.log_date = CURRENT_DATE - INTERVAL '1 day'
                WHERE v.member_id IS NULL AND a.member_id IS NULL AND mp.period_now_active = TRUE
            """)
            results = cursor.fetchall()
            print(f"결석 멤버 수: {len(results)}")
            
            if results:
                for result in results:
                    member_id = result[0]
                    member_nickname = result[1]
                    print(f"결석 멤버: {member_nickname} (ID: {member_id})")
                    # period_id 조회
                    cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = TRUE", (member_id,))
                    period_id_result = cursor.fetchone()
                    if period_id_result:
                        period_id = period_id_result[0]
                        print(f"결석 멤버: {member_nickname} (ID: {member_id})")
                        await process_absence(member_id, period_id, member_nickname)

            # 결석 3회 이상인 멤버 검색
            cursor.execute("""
                SELECT member_id FROM churn_prediction 
                WHERE prediction_absence_count >= 3 
                AND prediction_date <= (CURRENT_DATE - INTERVAL '1 day')
            """)
            results = cursor.fetchall()
            print(f"탈퇴 예정 멤버 수: {len(results)}")

            if results:
                for result in results:
                    member_id = result[0]
                    guild = discord.utils.get(client.guilds, id=1238886734725648496)  # 서버 ID로 서버 객체 가져오기
                    if guild:
                        member = discord.utils.get(guild.members, id=member_id)
                        if member:
                            await guild.kick(member, reason="스터디 조건 미달")
                            print(f"멤버 [{member.display_name}] 탈퇴 처리 완료")
                        else:
                            print(f"멤버 ID {member_id}를 서버에서 찾을 수 없습니다.")
                    else:
                        print(f"Guild with ID {1238886734725648496} not found")

        except Error as e:
            print(f"'{e}' 에러 발생")
        finally:
            cursor.close()
            connection.close()
            print("데이터베이스 연결 닫기")
    else:
        print("DB 연결 실패")


# 일일 공부 시간 순위 표시 함수 :: 매일 자정에 일일 순위 보여줌
@scheduler.scheduled_job('cron', hour=0, minute=0, day_of_week='tue-sun', timezone='Asia/Seoul')
async def send_daily_study_ranking():
    await client.wait_until_ready()
    print("send_daily_study_ranking 함수 시작")
    connection = create_db_connection()
    if connection:
        print("데이터베이스 연결 성공")
        cursor = connection.cursor()
        try:
            yesterday = (datetime.now(pytz.timezone('Asia/Seoul')) - timedelta(days=1)).strftime('%Y-%m-%d')
            print(f"기준 날짜: {yesterday}")
            print("일일 공부 시간 순위 계산을 시작합니다.")
            # 어제 공부한 멤버들의 공부시간 가져오기 (휴가 신청한 멤버도 포함)
            cursor.execute("""
                SELECT m.member_nickname, COALESCE(SUM(a.log_study_time), 0) AS total_study_time
                FROM member m
                LEFT JOIN activity_log a ON m.member_id = a.member_id AND a.log_date = %s
                WHERE m.member_id IN (
                    SELECT member_id FROM activity_log WHERE log_date = %s
                ) OR m.member_id IN (
                    SELECT member_id FROM vacation_log WHERE vacation_date = %s
                )
                GROUP BY m.member_nickname
                ORDER BY total_study_time DESC
            """, (yesterday, yesterday, yesterday))
            results = cursor.fetchall()
            print(f"쿼리 실행 결과: {results}")
            ranking_message = "@everyone\n======== 일일 공부시간 순위 ========\n"
            for i, (nickname, total_study_time) in enumerate(results, start=1):
                hours, minutes = divmod(total_study_time, 60)
                ranking_message += f"{i}등 {nickname} : {hours}시간 {minutes}분\n"

            if not results:
                ranking_message += "어제는 공부한 멤버가 없습니다.\n"

            ch = client.get_channel(1239098139361808429)
            if ch:
                print("채널 찾기 성공")
                await ch.send(ranking_message) # 순위 안내 메시지 보냄
            else:
                print("채널 찾기 실패")
        except Error as e:
            print(f"일일 공부 시간 순위를 계산하는 중 에러 발생: '{e}'")
        finally:
            cursor.close()
            connection.close()
            print("데이터베이스 연결 닫기")
    else:
        print("DB 연결 실패")


# 주간 공부 시간 순위 표시 함수 :: 월요일 자정에만 주간 순위 보여줌
@scheduler.scheduled_job('cron', day_of_week='mon', hour=0, minute=0, timezone='Asia/Seoul')
async def send_weekly_study_ranking():
    await client.wait_until_ready()
    print("send_weekly_study_ranking 함수 시작")
    connection = create_db_connection()
    if connection:
        print("데이터베이스 연결 성공")
        cursor = connection.cursor()
        try:
            print("주간 공부 시간 순위 계산을 시작합니다.")
            # 지난 주에 공부한 멤버들의 공부시간 가져오기
            cursor.execute("""
                SELECT m.member_nickname, SUM(a.log_study_time) AS total_study_time
                FROM activity_log a
                JOIN member m ON a.member_id = m.member_id
                WHERE a.log_date BETWEEN (CURRENT_DATE - INTERVAL '7 days') AND (CURRENT_DATE - INTERVAL '1 day')
                GROUP BY m.member_nickname, a.member_id
                ORDER BY total_study_time DESC
            """)
            results = cursor.fetchall()
            ranking_message = "@everyone\n======== 주간 공부시간 순위 ========\n"
            for i, (nickname, total_study_time) in enumerate(results, start=1):
                hours, minutes = divmod(total_study_time, 60)
                ranking_message += f"{i}등 {nickname} : {hours}시간 {minutes}분\n"

            if not results:
                ranking_message += "지난 주에는 공부한 멤버가 없습니다.\n"

            ch = client.get_channel(1239098139361808429)
            if ch:
                print("채널 찾기 성공")
                await ch.send(ranking_message) # 순위 안내 메시지 보냄
            else:
                print("채널 찾기 실패")
        except Error as e:
            print(f"주간 공부 시간 순위를 계산하는 중 에러 발생: '{e}'")
        finally:
            cursor.close()
            connection.close()
            print("데이터베이스 연결 닫기")
    else:
        print("DB 연결 실패")


# 스케줄러 시작
# if not scheduler.running:
#    scheduler.start()


# ---------------------------------------- Heroku 재시작 처리 ----------------------------------------
    
# 모든 세션 저장 함수
def save_all_sessions():
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
            # 현재 진행 중인 모든 세션 종료
            cursor.execute(
                "SELECT member_id, period_id FROM study_session WHERE session_end_time IS NULL"
            )
            results = cursor.fetchall()
            for member_id, period_id in results:
                cursor.execute(
                    "SELECT session_start_time FROM study_session WHERE member_id = %s AND period_id = %s ORDER BY session_id DESC LIMIT 1",
                    (member_id, period_id)
                )
                start_time_result = cursor.fetchone()
                if start_time_result:
                    start_time = start_time_result[0]
                    start_dt = start_time if isinstance(start_time, datetime) else datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                    end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                    duration = int((end_dt - start_dt).total_seconds() // 60)

                    # 종료 시간 업데이트
                    cursor.execute(
                        "UPDATE study_session SET session_end_time = %s, session_duration = %s WHERE member_id = %s AND period_id = %s AND session_end_time IS NULL",
                        (end_time, duration, member_id, period_id)
                    )

                    if duration >= 5:
                        day_duration, night_duration = calculate_day_night_duration(start_dt, end_dt)
                        log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')

                        cursor.execute(
                            "SELECT log_id, log_day_study_time, log_night_study_time FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                            (member_id, period_id, log_date)
                        )
                        log_result = cursor.fetchone()
                        
                        if log_result:
                            log_id, log_day_study_time, log_night_study_time = log_result
                            new_day_study_time = log_day_study_time + day_duration
                            new_night_study_time = log_night_study_time + night_duration
                            cursor.execute(
                                "UPDATE activity_log SET log_study_time = log_study_time + %s, log_day_study_time = %s, log_night_study_time = %s WHERE log_id = %s",
                                (duration, new_day_study_time, new_night_study_time, log_id)
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO activity_log (member_id, period_id, log_date, log_study_time, log_day_study_time, log_night_study_time) VALUES (%s, %s, %s, %s, %s, %s)",
                                (member_id, period_id, log_date, duration, day_duration, night_duration)
                            )
                            cursor.execute(
                                "SELECT log_id FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                                (member_id, period_id, log_date)
                            )
                            log_id = cursor.fetchone()[0]

                        if day_duration > night_duration:
                            active_period = 'Day'
                        elif night_duration > day_duration:
                            active_period = 'Night'
                        else:
                            active_period = 'Day'

                        cursor.execute(
                            "UPDATE activity_log SET log_active_period = %s WHERE log_id = %s",
                            (active_period, log_id)
                        )

            connection.commit()
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")


# 재시작 감지되면 미리 DB에 저장 후 안전히 종료할 수 있도록 함
def graceful_shutdown(signum, frame):
    print("Heroku 재부팅 감지됨. 안전하게 종료 중...")
    save_all_sessions()
    sys.exit(0)

# 시그널 등록
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)  # 로컬 테스트를 위한 SIGINT 핸들러 추가

# 재부팅 시 공부 종료/시작할 때도 똑같은 안내 보내기.
async def send_shutdown_messages():
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                "SELECT member_id, period_id FROM study_session WHERE session_end_time IS NULL"
            )
            results = cursor.fetchall()
            for member_id, period_id in results:
                cursor.execute(
                    "SELECT session_start_time FROM study_session WHERE member_id = %s AND period_id = %s ORDER BY session_id DESC LIMIT 1",
                    (member_id, period_id)
                )
                start_time_result = cursor.fetchone()
                if start_time_result:
                    start_time = start_time_result[0]
                    start_dt = start_time if isinstance(start_time, datetime) else datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                    end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                    duration = int((end_dt - start_dt).total_seconds() // 60)

                    # 종료 시간 업데이트
                    cursor.execute(
                        "UPDATE study_session SET session_end_time = %s, session_duration = %s WHERE member_id = %s AND period_id = %s AND session_end_time IS NULL",
                        (end_time, duration, member_id, period_id)
                    )

                    user = discord.utils.get(client.get_all_members(), id=member_id)
                    ch = client.get_channel(1239098139361808429)

                    if duration >= 5:
                        day_duration, night_duration = calculate_day_night_duration(start_dt, end_dt)
                        log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')

                        cursor.execute(
                            "SELECT log_id, log_day_study_time, log_night_study_time FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                            (member_id, period_id, log_date)
                        )
                        log_result = cursor.fetchone()

                        if log_result:
                            log_id, log_day_study_time, log_night_study_time = log_result
                            new_day_study_time = log_day_study_time + day_duration
                            new_night_study_time = log_night_study_time + night_duration
                            cursor.execute(
                                "UPDATE activity_log SET log_study_time = log_study_time + %s, log_day_study_time = %s, log_night_study_time = %s WHERE log_id = %s",
                                (duration, new_day_study_time, new_night_study_time, log_id)
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO activity_log (member_id, period_id, log_date, log_study_time, log_day_study_time, log_night_study_time) VALUES (%s, %s, %s, %s, %s, %s)",
                                (member_id, period_id, log_date, duration, day_duration, night_duration)
                            )
                            cursor.execute(
                                "SELECT log_id FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                                (member_id, period_id, log_date)
                            )
                            log_id = cursor.fetchone()[0]

                        if day_duration > night_duration:
                            active_period = 'Day'
                        elif night_duration > day_duration:
                            active_period = 'Night'
                        else:
                            active_period = 'Day'

                        cursor.execute(
                            "UPDATE activity_log SET log_active_period = %s WHERE log_id = %s",
                            (active_period, log_id)
                        )

                        if user:
                            await ch.send(f"{user.mention}님, {duration}분 동안 공부중!")
                    else:
                        if user:
                            await ch.send(f"{user.mention}님 공부 시간이 5분 미만이어서 기록되지 않았습니다.")
            connection.commit()
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# 봇이 재시작되었을 때 현재 카메라가 켜져있는 멤버들에 대해 새로운 세션을 시작하는 함수
async def start_sessions_for_active_cameras():
    await client.wait_until_ready()
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            guild = client.get_guild(1238886734725648496) 
            if guild:
                for channel in guild.voice_channels:
                    for member in channel.members:
                        if member.voice.self_video:  # 카메라가 켜져 있는지 확인
                            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
                            result = cursor.fetchone()
                            if result:
                                member_id = result[0]
                                cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = TRUE", (member_id,))
                                result = cursor.fetchone()
                                if result:
                                    period_id = result[0]
                                    start_study_session(member_id, period_id, member.display_name)
                                    ch = client.get_channel(1239098139361808429)
                                    await ch.send(f"{member.mention}님 공부 시작!✏️")
        except Error as e:
            print(f"'{e}' 에러 발생")
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# ---------------------------------------- 서버 참여 및 탈퇴 처리 ----------------------------------------

# 멤버 정보 & 멤버십 기간 등록
def insert_member_and_period(member):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # 멤버 정보가 이미 존재하는지 확인
            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
            result = cursor.fetchone()
            if result:
                member_id = result[0]
                # 현재 멤버가 있으면 기존 활동기간을 종료하고 새로운 활동 기간 등록
                cursor.execute(
                    "UPDATE membership_period SET period_now_active = %s, period_end_date = %s WHERE member_id = %s AND period_now_active = %s",
                    (False, datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d'), member_id, True)
                )
                cursor.execute(
                    "INSERT INTO membership_period (member_id, period_start_date, period_now_active) VALUES (%s, %s, %s)",
                    (member_id, datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d'), True)
                )
            else:
                # 멤버 정보 삽입
                join_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO member (member_nickname, member_username, member_join_date) VALUES (%s, %s, %s)",
                    (member.display_name, str(member), join_date)
                )
                # 새 member 등록 했으면 membership_period에도 등록
                cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
                member_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO membership_period (member_id, period_start_date, period_now_active) VALUES (%s, %s, %s)",
                    (member_id, datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d'), True)
                )
            connection.commit()
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")



# 멤버 탈퇴 처리
def handle_member_leave(member):
    connection = create_db_connection()

    if connection:
        cursor = connection.cursor()
        leave_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')

        try:
            # 멤버 정보 가져오기
            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
            result = cursor.fetchone()
            if result:
                member_id = result[0]
                # 현재 활성화된 기간을 비활성화하고 종료 날짜 업데이트
                cursor.execute(
                    "UPDATE membership_period SET period_now_active = %s, period_end_date = %s WHERE member_id = %s AND period_now_active = %s",
                    (False, leave_date, member_id, True)
                )
                connection.commit()
                print(f"[{member.display_name}]님의 탈퇴가 처리되었습니다. 탈퇴 날짜: {leave_date}")
            else:
                print(f"{member.display_name}님의 정보를 찾을 수 없습니다.")
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# ---------------------------------------- 공지 및 휴가신청 처리 ----------------------------------------       

# '공지' 입력 시 공지사항 출력 함수 
async def send_announcement(channel, author_mention):
    embed = discord.Embed(title="아아- 공지채널에서 알립니다.📢", description=f"{author_mention}님, 환영합니다!\n", 
                          timestamp=datetime.now(pytz.timezone('Asia/Seoul')), color=0x75c3c5)
    embed.add_field(name="📚 공부는 어떻게 시작하나요?", value="[study room] 음성 채널에서 카메라를 켜면 공부시간 측정 시작! \n카메라를 끄면 시간 측정이 종료됩니다. \n공부시간 5분 이하는 인정되지 않아요.\n\n", inline=False)
#    embed.add_field(name="⏰매일 5분 이상 공부해야 해요!", value="이 스터디의 목표는 [꾸준히 공부하는 습관]이에요. \n조금이라도 좋으니 매일매일 공부해보세요!\n", inline=False)
#    embed.add_field(name="🛏️쉬고싶은 날이 있나요?", value="[휴가신청] 채널에 \"휴가\"라고 남기면 돼요. (주 1회 가능) \n휴가를 사용해도 공부 가능하지만, 휴가를 취소할 수는 없어요. \n휴가를 제출한 날은 출석으로 인정됩니다.\n", inline=False)
#    embed.add_field(name="⚠️스터디 조건 미달", value="공부를 하지 않은 날이 3회 누적되는 경우 스터디에서 제외됩니다. \n하지만 언제든 다시 서버에 입장하여 도전할 수 있어요!\n", inline=False)
#    embed.add_field(name="📈내 공부시간 보기", value="다이렉트 메시지에서 \"공부시간\"이라고 입력하면, 봇이 지금까지의 공부시간을 알려드려요!\n", inline=False)
#    embed.add_field(name="📊공부시간 순위 공개", value="매일 자정에 일일 공부시간 순위가 공개됩니다.\n매주 월요일 0시에 주간 공부시간 순위가 공개됩니다.\n", inline=False)
    embed.set_footer(text="Bot made by.에옹", icon_url="https://cdn.discordapp.com/attachments/1238886734725648499/1238904212805648455/hamster-apple.png?ex=6640faf6&is=663fa976&hm=7e82b5551ae0bc4f4265c15c1ae0be3ef40ba7aaa621347baf1f46197d087fd6&")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1238886734725648499/1238905277777051738/file-0qJvNUQ1lyaUiZDmuOEI24BT.png?ex=6640fbf3&is=663faa73&hm=f2f65e3623da6c444361aa9938691d152623c88de4ca51852adc47e8b755289d&")
    await channel.send(embed=embed)        


# 휴가 신청 함수
async def process_vacation_request(message):
    if message.channel.id == 1238896271939338282:  # [휴가신청] 채널
        connection = create_db_connection()
        if connection:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(message.author),))
                result = cursor.fetchone()
                if result:
                    member_id = result[0]
                    cursor.close()

                    cursor = connection.cursor()  
                    # period_id 조회
                    cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = TRUE", (member_id,))
                    result = cursor.fetchone()
                    if result:
                        period_id = result[0]
                        cursor.close()
                        # insert_vacation_log 함수를 호출하여 휴가 기록 추가
                        success, response_message = insert_vacation_log(member_id, period_id, message.author)
                        await message.channel.send(response_message)
                    else:
                        await message.channel.send(f"{message.author.mention}님의 활동 기간을 찾을 수 없습니다.")
                else:
                    await message.channel.send(f"{message.author.mention}님의 정보를 찾을 수 없습니다.")
            except Error as e:
                print(f"'{e}' 에러 발생")
            finally:
                cursor.close()
                connection.close()
        else:
            await message.channel.send("DB 연결 실패")
    else:
        await message.channel.send(f"{message.author.mention}님, 휴가신청은 [휴가신청] 채널에서 부탁드려요!")


# 휴가 기록 추가 함수
def insert_vacation_log(member_id, period_id, member):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        vacation_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        vacation_week_start = (datetime.now(pytz.timezone('Asia/Seoul')) - timedelta(days=datetime.now(pytz.timezone('Asia/Seoul')).weekday())).strftime('%Y-%m-%d')

        try:
            # 이번 주에 이미 휴가를 사용했는지 확인
            cursor.execute(
                "SELECT vacation_date FROM vacation_log WHERE member_id = %s AND period_id = %s AND vacation_week_start = %s",
                (member_id, period_id, vacation_week_start)
            )
            result = cursor.fetchone()
            if result:
                already_used_date = result[0].strftime('%Y-%m-%d')
                return False, f"{member.mention}님, 이미 이번주에 휴가를 사용했어요! 휴가 사용일: {already_used_date}"

            # vacation_log 테이블에 기록 추가
            cursor.execute(
                "INSERT INTO vacation_log (member_id, period_id, vacation_date, vacation_week_start) VALUES (%s, %s, %s, %s)",
                (member_id, period_id, vacation_date, vacation_week_start)
            )

            # activity_log 테이블에 출석 기록 추가 또는 업데이트
            cursor.execute(
                "INSERT INTO activity_log (member_id, period_id, log_date, log_message_count, log_study_time, log_login_count, log_attendance) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (member_id, period_id, log_date) DO UPDATE SET log_attendance = EXCLUDED.log_attendance",
                (member_id, period_id, vacation_date, 0, 0, 0, True)
            )

            connection.commit()
            return True, f"{member.mention}님, 휴가신청이 완료되었습니다! 재충전하고 내일 만나요!☀️"
            
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
            return False, None

        finally:
            cursor.close()
            connection.close()
    else:
        return False, None



# ---------------------------------------- 공부 시작 및 종료 처리 ----------------------------------------

# 공부 세션 시작 정보 저장
def start_study_session(member_id, period_id, member_display_name):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        start_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
        try:
            cursor.execute(
                "INSERT INTO study_session (member_id, period_id, session_start_time, session_end_time) VALUES (%s, %s, %s, %s)",
                (member_id, period_id, start_time, None)
            )
            connection.commit()
            print(f"공부 세션 시작: 멤버 [{member_display_name}], 시작 시간 {start_time}")
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")


# 공부 세션 종료 정보 업데이트 -- 평소에 그냥 카메라 off 하여 공부 종료할 경우
async def end_study_session(member_id, period_id, member):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
        try:
            # 공부 시작 시간 가져오기
            cursor.execute(
                "SELECT session_start_time FROM study_session WHERE member_id = %s AND period_id = %s ORDER BY session_id DESC LIMIT 1",
                (member_id, period_id)
            )
            start_time_result = cursor.fetchone()
            if start_time_result is None:
                print(f"{member.display_name}님의 시작 시간이 등록되지 않았습니다.")
                return False, None
            start_time = start_time_result[0]
            if isinstance(start_time, str):
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            else:
                start_dt = start_time
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            duration = int((end_dt - start_dt).total_seconds() // 60)

            # 종료 시간 업데이트
            cursor.execute(
                "UPDATE study_session SET session_end_time = %s, session_duration = %s WHERE member_id = %s AND period_id = %s AND session_end_time IS NULL",
                (end_time, duration, member_id, period_id)
            )
            # 5분 이상인 경우에만 인정해줌
            if duration >= 5:
                # Day와 Night 시간 계산
                day_duration, night_duration = calculate_day_night_duration(start_dt, end_dt)

                # activity_log 업데이트
                log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
                # activity_log 테이블에 이미 해당 멤버 + 해당 날짜의 데이터 존재하면 업데이트
                cursor.execute(
                    "SELECT log_id, log_day_study_time, log_night_study_time FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                    (member_id, period_id, log_date)
                )
                log_result = cursor.fetchone()
                
                if log_result:
                    log_id, log_day_study_time, log_night_study_time = log_result
                    new_day_study_time = log_day_study_time + day_duration
                    new_night_study_time = log_night_study_time + night_duration
                    cursor.execute(
                        "UPDATE activity_log SET log_study_time = log_study_time + %s, log_day_study_time = %s, log_night_study_time = %s, log_attendance = %s WHERE log_id = %s",
                        (duration, new_day_study_time, new_night_study_time, True, log_id)
                    )
                else:
                    # activity_log에 데이터 없으면 새로 생성
                    cursor.execute(
                        "INSERT INTO activity_log (member_id, period_id, log_date, log_study_time, log_day_study_time, log_night_study_time, log_active_period, log_attendance) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (member_id, period_id, log_date, duration, day_duration, night_duration, 'Day' if day_duration >= night_duration else 'Night', True)
                    )
                    cursor.execute(
                        "SELECT log_id FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                        (member_id, period_id, log_date)
                    )
                    log_id = cursor.fetchone()[0]

                # Day와 Night 시간 계산 결과에 따른 공부 시간대 설정
                if day_duration > night_duration:
                    active_period = 'Day'
                elif night_duration > day_duration:
                    active_period = 'Night'
                else:
                    active_period = 'Day'  # Day와 Night 시간대가 같을 경우 Day로 설정

                cursor.execute(
                    "UPDATE activity_log SET log_active_period = %s WHERE log_id = %s",
                    (active_period, log_id)
                )

                connection.commit()
                return True, f"{member.mention}님 {duration}분 동안 공부했습니다!👍"
            else:
                connection.commit()
                return True, f"{member.mention}님 공부 시간이 5분 미만이어서 기록되지 않았습니다."
        except Exception as e:
            print(f"에러 발생: '{e}'")
            connection.rollback()
            return False, None
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")
        return False, None
    

# 공부 시간대 계산 함수
def calculate_day_night_duration(start_dt, end_dt):
    day_duration = 0
    night_duration = 0

    while start_dt < end_dt:
        if 6 <= start_dt.hour < 18:  # Day 시간대
            next_transition = datetime.combine(start_dt.date(), time(18, 0))
            if next_transition > end_dt:
                next_transition = end_dt
            day_duration += int((next_transition - start_dt).total_seconds() // 60)
        else:  # Night 시간대
            next_transition = datetime.combine(start_dt.date() + timedelta(days=1), time(6, 0))
            if start_dt.hour < 6:
                next_transition = datetime.combine(start_dt.date(), time(6, 0))
            if next_transition > end_dt:
                next_transition = end_dt
            night_duration += int((next_transition - start_dt).total_seconds() // 60)
        start_dt = next_transition

    return day_duration, night_duration


# 매일 11시 59분이 되면 공부 정보를 모두 저장함 + 0시 0분에 카메라 켜져있는 멤버 공부 시작시킴
async def end_study_session_at_midnight():
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d 23:59:59')
            # 현재 진행 중인 모든 세션을 종료
            cursor.execute(
                "SELECT member_id, period_id FROM study_session WHERE session_end_time IS NULL"
            )
            results = cursor.fetchall()
            for member_id, period_id in results:
                await end_study_session(member_id, period_id, "자동 종료")

            # 카메라가 켜져 있는 멤버들의 새로운 공부 세션 시작
            cursor.execute(
                """
                SELECT DISTINCT ss.member_id, mp.period_id
                FROM study_session ss
                JOIN membership_period mp ON ss.member_id = mp.member_id
                WHERE ss.session_end_time = %s AND mp.period_now_active = TRUE
                """,
                (end_time,)
            )
            member_ids = cursor.fetchall()
            for member_id, period_id in member_ids:
                start_study_session(member_id, period_id, "자동 시작")
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")


# ---------------------------------------- 결석 처리 ----------------------------------------

# 멤버 결석 처리 함수 -- 결석 시 안내 // 결석 3회 시 안내 후 탈퇴처리 (다이렉트 메세지로)
async def process_absence(member_id, period_id, member_display_name):
    print(f"process_absence 시작: 멤버 ID {member_id}, 기간 ID {period_id}")
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        absence_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        try:
            # 현재 결석 일수 가져오기
            cursor.execute(
                "SELECT COUNT(*) FROM churn_prediction WHERE member_id = %s AND period_id = %s",
                (member_id, period_id)
            )
            absence_count = cursor.fetchone()[0] + 1
            print(f"현재 결석 일수: {absence_count - 1}, 새로운 결석 일수: {absence_count}")

            # 결석 기록 추가
            cursor.execute(
                "INSERT INTO churn_prediction (member_id, period_id, prediction_date, prediction_absence_count, prediction_risk_level) VALUES (%s, %s, %s, %s, %s)",
                (member_id, period_id, absence_date, absence_count, get_risk_level(absence_count))
            )

            connection.commit()
            print(f"{member_display_name}님의 결석이 기록되었습니다. 결석 일수: {absence_count}")

            # 1회, 2회 결석한 경우 - 결석 기록 안내 다이렉트 메시지 전송
            user = discord.utils.get(client.get_all_members(), id=member_id)
            if user:
                try:
                    print(f"DM 전송 시도: {member_display_name} ({user.name})")
                    await user.send(f"{member_display_name}님, 결석이 기록되었습니다. 현재 {absence_count}회 결석하셨습니다.")
                    print(f"{member_display_name}님에게 결석 기록 메시지가 전송되었습니다.")
                except discord.Forbidden:
                    print(f"DM을 보낼 수 없습니다: {member_display_name}")
                except Exception as e:
                    print(f"DM 전송 중 에러 발생: {e}")
            else:
                print(f"멤버를 찾을 수 없습니다: {member_display_name}")

            # 3회 결석한 경우 - 탈퇴 예정 안내 다이렉트 메시지 전송
            if absence_count >= 3:
                if user:
                    try:
                        await user.send(f"{member_display_name}님, 3회 결석하였습니다. 익일 탈퇴 처리됩니다. 탈퇴 정보는 본인만 알 수 있으며, 언제든 다시 스터디 참여 가능합니다! 기다리고 있을게요🙆🏻")
                        print(f"{member_display_name}님에게 탈퇴 예정 메시지가 전송되었습니다.")
                    except discord.Forbidden:
                        print(f"DM을 보낼 수 없습니다: {member_display_name}")
                    except Exception as e:
                        print(f"탈퇴 예정 메시지 전송 중 에러 발생: {e}")

        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
            print("데이터베이스 연결 닫기")
    else:
        print("DB 연결 실패")

    
# 결석일수에 따라 이탈 위험 수준 결정
def get_risk_level(absence_count):
    if absence_count == 1:
        return 'Low'
    elif absence_count == 2:
        return 'Moderate'
    else:
        return 'High'
   

# ---------------------------------------- 공부시간 안내 ----------------------------------------

# 공부시간 안내 함수 (휴가 신청했어도 실제 공부시간으로 안내되도록)
async def send_study_time_info(user, member_id, period_id):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # 오늘 공부시간
            cursor.execute(
                """
                SELECT COALESCE(SUM(log_study_time), 0) 
                FROM activity_log 
                WHERE member_id = %s 
                AND period_id = %s 
                AND log_date = CURRENT_DATE
                """,
                (member_id, period_id)
            )
            today_study_time = cursor.fetchone()[0]

            # 이번 주 공부시간
            cursor.execute(
                """
                SELECT COALESCE(SUM(log_study_time), 0) 
                FROM activity_log
                WHERE member_id = %s 
                AND period_id = %s
                AND log_date >= CURRENT_DATE - EXTRACT(DOW FROM CURRENT_DATE) * INTERVAL '1 day'
                AND log_date <= CURRENT_DATE
                """,
                (member_id, period_id)
            )
            week_study_time = cursor.fetchone()[0]

            # 누적 공부시간
            cursor.execute(
                """
                SELECT COALESCE(SUM(log_study_time), 0) 
                FROM activity_log
                WHERE member_id = %s 
                AND period_id = %s
                """,
                (member_id, period_id)
            )
            total_study_time = cursor.fetchone()[0]

            # 시간과 분으로 변환
            today_hours, today_minutes = divmod(today_study_time, 60)
            week_hours, week_minutes = divmod(week_study_time, 60)
            total_hours, total_minutes = divmod(total_study_time, 60)

            await user.send(
                f"{user.mention}님, 현재까지의 공부시간을 알려드릴게요!\n"
                f"1. 오늘 공부시간 : {today_hours}시간 {today_minutes}분\n"
                f"2. 이번 주 공부시간 : {week_hours}시간 {week_minutes}분\n"
                f"3. 누적 공부시간 : {total_hours}시간 {total_minutes}분"
            )
        except Error as e:
            print(f"'{e}' 에러 발생")
        finally:
            cursor.close()
            connection.close()
    else:
        await user.send("DB 연결 실패")



# ---------------------------------------- 데이터 수집 ----------------------------------------


# 메시지 수 카운팅하는 함수
def log_message_count(member_id):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        try:
            # 이미 해당 멤버와 날짜에 대한 로그가 존재하는지 확인
            cursor.execute(
                "SELECT log_id FROM activity_log WHERE member_id = %s AND log_date = %s",
                (member_id, log_date)
            )
            log_id = cursor.fetchone()
            if log_id:
                # 이미 존재하는 로그가 있으면 메시지 수 업데이트
                cursor.execute(
                    "UPDATE activity_log SET log_message_count = log_message_count + 1 WHERE log_id = %s",
                    (log_id[0],)
                )
            else:
                # 존재하지 않으면 새로운 로그 생성
                cursor.execute(
                    "INSERT INTO activity_log (member_id, period_id, log_date, log_message_count, log_study_time, log_day_study_time, log_night_study_time, log_attendance, log_login_count, log_reaction_count, log_active_period) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (member_id, get_active_period_id(member_id), log_date, 1, 0, 0, 0, False, 0, 0, 'Day')
                )
            connection.commit()
        except Exception as e:
            print(f"Error logging message count: {e}")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# 메시지 수 카운팅하기 위해 활동중인 Period_id 가져오는 함수
def get_active_period_id(member_id):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = TRUE",
                (member_id,)
            )
            period_id = cursor.fetchone()
            if period_id:
                return period_id[0]
        except Exception as e:
            print(f"Error getting active period id: {e}")
        finally:
            cursor.close()
            connection.close()
    return None

# 로그인 횟수를 기록하는 함수 (활동 상태가 온라인으로 변하면 로그인했다고 본다.)
def log_login_count(member_id):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        try:
            # 이미 해당 멤버와 날짜에 대한 로그가 존재하는지 확인
            cursor.execute(
                "SELECT log_id, log_login_count FROM activity_log WHERE member_id = %s AND log_date = %s",
                (member_id, log_date)
            )
            log_id = cursor.fetchone()
            if log_id:
                # 이미 존재하는 로그가 있으면 로그인 수 업데이트
                current_count = log_id[1]
                if current_count < 2147483647:  # Check if the current count is within the integer range
                    cursor.execute(
                        "UPDATE activity_log SET log_login_count = log_login_count + 1 WHERE log_id = %s",
                        (log_id[0],)
                    )
            else:
                # 존재하지 않으면 새로운 로그 생성
                cursor.execute(
                    "INSERT INTO activity_log (member_id, period_id, log_date, log_message_count, log_study_time, log_day_study_time, log_night_study_time, log_attendance, log_login_count, log_reaction_count, log_active_period) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (member_id, get_active_period_id(member_id), log_date, 0, 0, 0, 0, False, 1, 0, 'Day')
                )
            connection.commit()
        except Exception as e:
            print(f"Error logging login count: {e}")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")
    

# 반응 횟수를 기록하는 함수
def log_reaction_count(member_id):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        try:
            # 이미 해당 멤버와 날짜에 대한 로그가 존재하는지 확인
            cursor.execute(
                "SELECT log_id FROM activity_log WHERE member_id = %s AND log_date = %s",
                (member_id, log_date)
            )
            log_id = cursor.fetchone()
            if log_id:
                # 이미 존재하는 로그가 있으면 반응 수 업데이트
                cursor.execute(
                    "UPDATE activity_log SET log_reaction_count = log_reaction_count + 1 WHERE log_id = %s",
                    (log_id[0],)
                )
            else:
                # 존재하지 않으면 새로운 로그 생성
                cursor.execute(
                    "INSERT INTO activity_log (member_id, period_id, log_date, log_message_count, log_study_time, log_day_study_time, log_night_study_time, log_attendance, log_login_count, log_reaction_count, log_active_period) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (member_id, get_active_period_id(member_id), log_date, 0, 0, 0, 0, False, 0, 1, 'Day')
                )
            connection.commit()
        except Exception as e:
            print(f"Error logging reaction count: {e}")
            connection.rollback()
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

        
# ================================================ 서버 이벤트 ================================================


# 봇이 실행중일 때 상태메시지
@client.event
async def on_ready():
    print("봇 실행을 시작합니다.")
    await client.change_presence(status=discord.Status.online, activity=discord.Game("공부 안하고 딴짓"))
    
    if not scheduler.running:
        scheduler.start()

#    테스트용 스케줄러 추가
#    run_date = datetime.now(pytz.timezone('Asia/Seoul')) + timedelta(minutes=1)  # 일일 및 주간 순위 테스트 시 활성화
#    scheduler.add_job(send_daily_study_ranking, 'date', run_date=run_date) # 일일 순위 1분 후 테스트
#    scheduler.add_job(send_weekly_study_ranking, 'date', run_date=run_date) # 주간 순위 1분 후 테스트
    await check_absences()  # 결석 처리 함수 테스트

    await start_sessions_for_active_cameras()  # 봇 재시작 후 카메라 상태 확인 및 공부 세션 시작


# 멤버 새로 참여 시 [member]와 [membership_period]테이블에 정보 추가 및 공지 출력
@client.event
async def on_member_join(member):
    print(f'[{member.display_name}]님이 서버에 참여했습니다.')
    insert_member_and_period(member)
    ch = client.get_channel(1238886734725648499)
    await send_announcement(ch, member.mention)
 

# 멤버 탈퇴 시 [membership_period]테이블에 정보 업데이투
@client.event
async def on_member_remove(member):
    print(f'[{member.display_name}]님이 서버를 탈퇴했습니다.') # 파이썬 터미널에 출력됨!
    handle_member_leave(member)


#  메시지 수 카운팅 / '공지' 명령어 입력 시 공지사항 출력 / 
# '휴가신청' 입력 시 휴가신청 / '공부시간' 입력 시 공부시간 안내

@client.event
async def on_message(message):
    if message.author == client.user:
        return  # 봇 자신의 메시지는 무시

    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(message.author),))
            result = cursor.fetchone()
            if result:
                member_id = result[0]
                log_message_count(member_id)  # 메시지 전송 횟수 로그 함수 호출
            else:
                print(f"Member {message.author} not found in the database.")
        except Exception as e:
            print(f"Error fetching member ID: {e}")
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

    if message.content == "공지":
        if message.channel.id == 1238886734725648499: # [공지]채널
            await send_announcement(message.channel, message.author.mention) # 공지 함수 호출
        else:
            await message.channel.send(f"{message.author.mention}님, 공지사항은 [공지] 채널에서 볼 수 있어요!")
    
    if message.content == "휴가신청":
        await process_vacation_request(message) # 휴가신청 함수 호출
    
    if message.content == "공부시간":
        if isinstance(message.channel, discord.DMChannel):
            connection = create_db_connection()
            if connection:
                cursor = connection.cursor()
                cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(message.author),))
                result = cursor.fetchone()
                if result:
                    member_id = result[0]
                    cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = TRUE", (member_id,))
                    result = cursor.fetchone()
                    if result:
                        period_id = result[0]
                        await send_study_time_info(message.author, member_id, period_id)
                    else:
                        await message.author.send("활동 기간을 찾을 수 없습니다.")
                else:
                    await message.author.send("회원 정보를 찾을 수 없습니다.")
                cursor.close()
                connection.close()
            else:
                await message.author.send("DB 연결 실패")
        else:
            await message.channel.send(f"{message.author.mention}님, 채널이 아닌 [다이렉트 메시지]로 study bot에게 '공부시간'을 질문해보세요! 현재까지 공부한 시간을 알려드릴게요.")


# 공부 시작 / 공부 종료 함수 -- 오류 해결 때문에 각각 로그 추가!
@client.event
async def on_voice_state_update(member, before, after):
    ch = client.get_channel(1239098139361808429)
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # 멤버 정보 가져오기
            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
            result = cursor.fetchone()
            if result:
                member_id = result[0]
            else:
                cursor.close()
                connection.close()
                return  # 멤버 정보가 없으면 함수 종료

            # 활동 기간 ID 가져오기
            cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = TRUE", (member_id,))
            result = cursor.fetchone()
            if result:
                period_id = result[0]
            else:
                cursor.close()
                connection.close()
                return  # 활동 기간 정보가 없으면 함수 종료

            cursor.close()
            connection.close()

            # 음성 채널에 들어가서 카메라를 켰을 때 공부 시작
            if after.channel is not None and after.self_video and (before.channel is None or not before.self_video):
                await ch.send(f"{member.mention}님 공부 시작!✏️")
                start_study_session(member_id, period_id, member.display_name)

            # 카메라가 켜져 있는 상태에서 음성 채널을 나가거나 카메라를 끌 때 공부 종료
            elif before.channel is not None and before.self_video and (after.channel is None or not after.self_video):
                print(f"{member.display_name}님의 공부 세션을 종료합니다.")
                success, message = await end_study_session(member_id, period_id, member)
                if success and message:
                    await ch.send(message)  # 공부기록됐다~ 메시지 전송
                else:
                    print(f"{member.display_name}님의 공부 세션 종료 실패")

        except Exception as e:
            print(f"에러 발생: '{e}'")
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")


# 멤버의 상태 변화 감지하여 로그인 횟수 기록
@client.event
async def on_presence_update(before, after):
    if before.status == discord.Status.offline and after.status == discord.Status.online:
        log_login_count(after.id)


# 반응 추가 이벤트 감지하여 반응 횟수 기록
@client.event
async def on_reaction_add(reaction, user):
    if not user.bot:  # 봇의 반응은 무시
        print(f" {user.name} ({user.id}) 님이 메시지 ({reaction.message.id})에 반응을 남겼습니다.") # 로그 추가
        log_reaction_count(user.id)




# ---- 토큰


# 봇 실행 토큰
client.run(token)
