import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
import asyncio
import mysql.connector
from mysql.connector import Error
from datetime import datetime, time, timedelta
import pytz
import signal
import sys


# .env 파일의 환경 변수를 로드 (로컬에서 토큰 가져오기)
load_dotenv()

# Heroku 환경 변수에서 토큰 가져오기
token = os.getenv('TOKEN')

# 데이터베이스 연결 설정
def create_db_connection():
    try:
        connection = mysql.connector.connect(
            host='127.0.0.1',  # 또는 'localhost' 그대로 유지
            user='root',
            password='0626',
            database='study_bot',
            port=3307  # 사용 중인 포트 번호 추가
        )
        return connection
    except Error as e:
        print(f"'{e}' 에러 발생")
        return None
    
# ---------------------------------------- Heroku에서 24시간마다 서버 재시작함 :: 재시작 감지되면 직전까지의 데이터 저장하는 함수 ----------------------------------------
    
# 모든 세션 저장 함수
def save_all_sessions():
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        try:
            end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
            # 현재 진행 중인 모든 세션을 종료
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
                    if isinstance(start_time, str):
                        start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                    else:
                        start_dt = start_time
                    end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                    duration = int((end_dt - start_dt).total_seconds() // 60)
                    cursor.execute(
                        "UPDATE study_session SET session_end_time = %s, session_duration = %s WHERE member_id = %s AND period_id = %s AND session_end_time IS NULL",
                        (end_time, duration, member_id, period_id)
                    )
                    if duration >= 5:
                        log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
                        cursor.execute(
                            "SELECT log_id FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                            (member_id, period_id, log_date)
                        )
                        log_id = cursor.fetchone()
                        if log_id:
                            cursor.execute(
                                "UPDATE activity_log SET log_study_time = log_study_time + %s WHERE log_id = %s",
                                (duration, log_id[0])
                            )
                        else:
                            cursor.execute(
                                "INSERT INTO activity_log (member_id, period_id, log_date, log_study_time) VALUES (%s, %s, %s, %s)",
                                (member_id, period_id, log_date, duration)
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


# Graceful Shutdown 핸들러 :: 재시작 감지되면 미리 DB에 저장 후 안전히 종료할 수 있도록 함
def graceful_shutdown(signum, frame):
    print("안전하게 종료중...")
    save_all_sessions()
    sys.exit(0)

# 시그널 등록
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)  # 로컬 테스트를 위한 SIGINT 핸들러 추가


# 봇이 재시작되었을 때 현재 카메라가 켜져있는 멤버들에 대해 새로운 세션을 시작하는 함수
async def start_sessions_for_active_cameras():
    await client.wait_until_ready()
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        try:
            guild = client.get_guild(1238886734725648496) 
            if guild:
                for channel in guild.voice_channels:
                    for member in channel.members:
                        if member.self_video:  # 카메라가 켜져 있는지 확인
                            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
                            result = cursor.fetchone()
                            if result:
                                member_id = result[0]
                                cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = 1", (member_id,))
                                result = cursor.fetchone()
                                if result:
                                    period_id = result[0]
                                    start_study_session(member_id, period_id, member.display_name)
                                    ch = client.get_channel(1239098139361808429)
                                    await ch.send(f"{member.display_name}님 공부 시작!✏️")
        except Error as e:
            print(f"'{e}' 에러 발생")
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# ---------------------------------------- 서버 참여 / 서버 탈퇴 함수 ----------------------------------------

# 멤버 정보 & 멤버십 기간 등록
def insert_member_and_period(member):
    connection = create_db_connection()

    if connection:
        cursor = connection.cursor(buffered=True)  # buffered=True 추가 : 쿼리문 처리가 끝나기 전에 다음 쿼리문이 실행되는 문제 수정
        
        try:
            # 멤버 정보가 이미 존재하는지 확인
            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
            result = cursor.fetchone()
            if result:
                member_id = result[0]
                print(f"[{member.display_name}] 해당 멤버가 이미 등록되어 있습니다. [ID : {member_id}]")
                # 기존 멤버가 있으면 현재 활성화된 기간을 비활성화하고 새로운 기간을 등록
                cursor.execute(
                    "UPDATE membership_period SET period_now_active = 0, period_end_date = %s WHERE member_id = %s AND period_now_active = 1",
                    (datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d'), member_id)
                )
                cursor.close()
                cursor = connection.cursor(buffered=True)
                cursor.execute(
                    "INSERT INTO membership_period (member_id, period_start_date, period_now_active) VALUES (%s, %s, %s)",
                    (member_id, datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d'), 1)
                )

            else:
                # 멤버 정보 삽입
                join_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute(
                    "INSERT INTO member (member_nickname, member_username, member_join_date) VALUES (%s, %s, %s)",
                    (member.display_name, str(member), join_date)
                )
                member_id = cursor.lastrowid
                print(f"새로운 멤버 [{member.display_name}]가 등록되었습니다. [ID : {member_id}]")

                # 새 멤버 등록 후 membership_period 테이블에 기간 등록
                cursor.execute(
                    "INSERT INTO membership_period (member_id, period_start_date, period_now_active) VALUES (%s, %s, %s)",
                    (member_id, datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d'), 1)
                )
            connection.commit()
            print(f"[{member.display_name}] 해당 멤버의 멤버십이 시작되었습니다.")
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
        cursor = connection.cursor(buffered=True)
        leave_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')

        try:
            # 멤버 정보 가져오기
            cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(member),))
            result = cursor.fetchone()
            if result:
                member_id = result[0]
                # 현재 활성화된 기간을 비활성화하고 종료 날짜 업데이트
                cursor.execute(
                    "UPDATE membership_period SET period_now_active = 0, period_end_date = %s WHERE member_id = %s AND period_now_active = 1",
                    (leave_date, member_id)
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

# ---------------------------------------- 공지 관련 함수 ----------------------------------------       

# '공지' 입력 시 공지사항 출력 함수
async def send_announcement(channel, author_mention):
    embed = discord.Embed(title="아아- 공지채널에서 알립니다.📢", description=f"{author_mention}님, 환영합니다!\n", 
                          timestamp=datetime.now(pytz.timezone('Asia/Seoul')), color=0x75c3c5)
    embed.add_field(name="📚 공부는 어떻게 시작하나요?", value="[study room] 채널에서 카메라를 켜면 공부시간 측정 시작! \n카메라를 끄면 시간 측정이 종료되고, \n일일 공부시간에 누적돼요. \n공부시간 5분 이하는 인정되지 않아요.\n\n", inline=False)
    embed.add_field(name="⏰매일 5분 이상 공부해야 해요!", value="이 스터디의 목표는 [꾸준히 공부하는 습관]이에요. \n조금이라도 좋으니 매일매일 공부해보세요!\n", inline=False)
    embed.add_field(name="✍️ 카메라로 얼굴을 꼭 보여줘야 하나요?", value="아니요! 공부하는 모습을 부분적으로 보여준다면 다 좋아요. \nex) 공부하는 손, 타이핑하는 키보드, 종이가 넘어가는 책... \n물론 얼굴을 보여준다면 반갑게 인사할게요.\n", inline=False)
    embed.add_field(name="🛏️쉬고싶은 날이 있나요?", value="채팅 채널 [휴가신청]에 \"휴가\"라고 남기면 돼요. (주 1회 가능) \n휴가를 사용해도 공부 가능하지만, 휴가를 취소할 수는 없어요. \n휴가를 제출한 날은 공부한 것으로 인정됩니다.\n", inline=False)
    embed.add_field(name="⚠️스터디 조건 미달", value="공부를 하지 않은 날이 3회 누적되는 경우 스터디에서 제외됩니다. \n하지만 언제든 다시 서버에 입장하여 도전할 수 있어요!\n", inline=False)
    embed.add_field(name="📈내 공부시간 보기", value="다이렉트 메시지에서 \"공부시간\"이라고 입력하면, 봇이 지금까지의 공부시간을 1:1로 알려드려요!\n", inline=False)
    embed.add_field(name="📊공부시간 순위 공개", value="매일 자정에 일일 공부시간 순위가 공개됩니다.\n매주 월요일 0시에 주간 공부시간 순위가 공개됩니다.\n", inline=False)
    embed.set_footer(text="Bot made by.에옹", icon_url="https://cdn.discordapp.com/attachments/1238886734725648499/1238904212805648455/hamster-apple.png?ex=6640faf6&is=663fa976&hm=7e82b5551ae0bc4f4265c15c1ae0be3ef40ba7aaa621347baf1f46197d087fd6&")
    embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1238886734725648499/1238905277777051738/file-0qJvNUQ1lyaUiZDmuOEI24BT.png?ex=6640fbf3&is=663faa73&hm=f2f65e3623da6c444361aa9938691d152623c88de4ca51852adc47e8b755289d&")
    await channel.send(embed=embed)        


# ---------------------------------------- 공부 시작 / 공부 종료 함수 ----------------------------------------

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
async def end_study_session(member_id, period_id, member_display_name):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
        try:
            # 시작 시간 가져오기
            cursor.execute(
                "SELECT session_start_time FROM study_session WHERE member_id = %s AND period_id = %s ORDER BY session_id DESC LIMIT 1",
                (member_id, period_id)
            )
            start_time_result = cursor.fetchone()
            if start_time_result is None:
                print(f"{member_display_name}님의 시작 시간이 등록되지 않았습니다.")
                return False, None
            start_time = start_time_result[0]
            # 시작 시간이 datetime 객체가 아닌 경우 문자열로 변환
            if isinstance(start_time, str):
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            else:
                start_dt = start_time
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            duration = int((end_dt - start_dt).total_seconds() // 60)
            # 종료 시간 및 기간 업데이트
            cursor.execute(
                "UPDATE study_session SET session_end_time = %s, session_duration = %s WHERE member_id = %s AND period_id = %s AND session_end_time IS NULL",
                (end_time, duration, member_id, period_id)
            )
            connection.commit()
            # 공부 시간이 5분 이상인 경우에만 activity_log 테이블의 log_study_time에 공부시간 누적
            if duration >= 5:
                # activity_log에 해당 날짜와 멤버의 레코드가 존재하는지 확인
                log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
                cursor.execute(
                    "SELECT log_id FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                    (member_id, period_id, log_date)
                )
                log_id = cursor.fetchone()
                if log_id:
                    # 이미 존재하는 레코드에 공부 시간 누적
                    cursor.execute(
                        "UPDATE activity_log SET log_study_time = log_study_time + %s WHERE log_id = %s",
                        (duration, log_id[0])
                    )
                else:
                    # 새로운 레코드 삽입
                    cursor.execute(
                        "INSERT INTO activity_log (member_id, period_id, log_date, log_study_time) VALUES (%s, %s, %s, %s)",
                        (member_id, period_id, log_date, duration)
                    )
                message = f"{member_display_name}님 {duration}분 동안 공부했습니다!👍"
                print(f"{member_display_name}님의 최근 공부 시간: {duration}분")
            else:
                message = f"{member_display_name}님 공부 시간이 5분 미만이어서 기록되지 않았습니다."
                print(f"{member_display_name}님의 공부 시간이 5분 미만이어서 기록되지 않았습니다.")
            connection.commit()
            return True, message
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
            return False, None
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")
        return False, None
    

# 매일 11시 59분이 되면 공부 정보를 모두 저장함 + 0시 0분에 카메라 켜져있는 멤버 공부 시작시킴
async def end_study_session_at_midnight():
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
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
                WHERE ss.session_end_time = %s AND mp.period_now_active = 1
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


# 자정에 end_study_session_at_midnight 함수 예약
@tasks.loop(hours=24)
async def schedule_midnight_tasks():
    await client.wait_until_ready()
    now = datetime.now(pytz.timezone('Asia/Seoul'))
    target_time = now.replace(hour=23, minute=59, second=0, microsecond=0)
    while True:
        now = datetime.now(pytz.timezone('Asia/Seoul'))
        if now >= target_time:
            await end_study_session_at_midnight()
            target_time = target_time + timedelta(days=1)
        await asyncio.sleep(1)

# ---------------------------------------- 결석일수 관리 함수 ----------------------------------------
# 멤버 결석 처리 함수
def process_absence(member_id, period_id, member_display_name):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        absence_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')

        try:
            # 현재 결석 일수 가져오기
            cursor.execute(
                "SELECT COUNT(*) FROM churn_prediction WHERE member_id = %s AND period_id = %s",
                (member_id, period_id)
            )
            absence_count = cursor.fetchone()[0] + 1

            # 결석 기록 추가
            cursor.execute(
                "INSERT INTO churn_prediction (member_id, period_id, prediction_date, prediction_absence_count, prediction_risk_level) VALUES (%s, %s, %s, %s, %s)",
                (member_id, period_id, absence_date, absence_count, get_risk_level(absence_count))
            )

            connection.commit()
            print(f"{member_display_name}님의 결석이 기록되었습니다. 결석 일수: {absence_count}")

            # 결석 일수가 3일 이상인 경우 안내 메시지 반환
            if absence_count >= 3:
                return f"{member_display_name}님, 3회 결석하였습니다. 익일 탈퇴 처리됩니다. 탈퇴 정보는 본인만 알 수 있으며, 언제든 다시 스터디 참여 가능합니다! 기다리고 있을게요🙆🏻"
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
            return None
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")
        return None
    
# 결석일수에 따라 이탈 위험 수준 결정
def get_risk_level(absence_count):
    if absence_count == 1:
        return 'Low'
    elif absence_count == 2:
        return 'Moderate'
    else:
        return 'High'
    
# 매일 0시에 전날 결석 체크 + 결석 3회 시 익일에 탈퇴 처리
@tasks.loop(hours=24)  # 실제 코드에서는 hour=24로 변경
async def check_absences():
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        try:
            # 휴가 또는 출석한 멤버를 제외한 나머지 멤버 찾기
            cursor.execute("""
                SELECT m.member_id, m.member_username
                FROM member m
                LEFT JOIN vacation_log v ON m.member_id = v.member_id AND v.vacation_date = CURDATE()
                LEFT JOIN study_session s ON m.member_id = s.member_id AND s.session_start_time >= CURDATE()
                WHERE v.member_id IS NULL AND s.member_id IS NULL
            """)
            results = cursor.fetchall()

            if results:
                for result in results:
                    member_id = result[0]
                    member_username = result[1]
                    process_absence(member_id, 1, member_username)  # period_id 값을 1로 가정

            # 결석 3회 이상인 멤버 검색
            cursor.execute(
                "SELECT member_id, member_username FROM churn_prediction WHERE prediction_absence_count >= 3 AND DATE(prediction_date) <= DATE_SUB(NOW(), INTERVAL 1 DAY)"
            )
            results = cursor.fetchall()

            if results:
                for result in results:
                    member_id = result[0]
                    member_username = result[1]
                    user = discord.utils.get(client.get_all_members(), name=member_username)
                    if user:
                        try:
                            await user.send(f"{user.display_name}님, 3회 결석하였습니다. 익일 탈퇴 처리됩니다. 탈퇴 정보는 본인만 알 수 있으며, 언제든 다시 스터디 참여 가능합니다! 기다리고 있을게요🙆🏻")
                        except discord.Forbidden:
                            print(f"DM을 보낼 수 없습니다: {member_username}")

            # 익일 0시에 탈퇴 처리
            await asyncio.sleep(86400)  # 24시간 대기
            if results:
                for result in results:
                    member_id = result[0]
                    member_username = result[1]
                    guild = discord.utils.get(client.guilds, id=1238886734725648496)  # 서버 ID로 서버 객체 가져오기
                    if guild:
                        member = discord.utils.get(guild.members, name=member_username)
                        if member:
                            await guild.kick(member, reason="스터디 조건 미달")
                        else:
                            print(f"Member {member_username} not found in guild {guild.name}")
                    else:
                        print(f"Guild with ID {1238886734725648496} not found")

        except Error as e:
            print(f"'{e}' 에러 발생")
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")



        
# ---------------------------------------- 휴가 신청 함수 ----------------------------------------

# 휴가 신청 함수
async def process_vacation_request(message):
    if message.channel.id == 1238896271939338282:  # [휴가신청] 채널
        connection = create_db_connection()
        if connection:
            cursor = connection.cursor(buffered=True)
            try:
                cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(message.author),))
                result = cursor.fetchone()
                if result:
                    member_id = result[0]
                    cursor.close()

                    cursor = connection.cursor(buffered=True)  # period_id 조회
                    cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = 1", (member_id,))
                    result = cursor.fetchone()
                    if result:
                        period_id = result[0]
                        cursor.close()
                        # insert_vacation_log 함수를 호출하여 휴가 기록 추가
                        success, response_message = insert_vacation_log(member_id, period_id, message.author.display_name)
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
def insert_vacation_log(member_id, period_id, member_display_name):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
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
                return False, f"{member_display_name}님, 이미 이번주에 휴가를 사용했어요! 휴가 사용일: {already_used_date}"

            # vacation_log 테이블에 기록 추가
            cursor.execute(
                "INSERT INTO vacation_log (member_id, period_id, vacation_date, vacation_week_start) VALUES (%s, %s, %s, %s)",
                (member_id, period_id, vacation_date, vacation_week_start)
            )

            # activity_log 테이블에 출석 기록 추가 또는 업데이트
            cursor.execute(
                "INSERT INTO activity_log (member_id, period_id, log_date, log_message_count, log_study_time, log_login_count, log_attendance) VALUES (%s, %s, %s, %s, %s, %s, %s) ON DUPLICATE KEY UPDATE log_attendance = VALUES(log_attendance)",
                (member_id, period_id, vacation_date, 0, 0, 0, True)
            )

            connection.commit()
            print(f"{member_display_name}님의 휴가신청 완료되었습니다. [날짜 : {vacation_date}]")
            return True, f"{member_display_name}님, 휴가신청이 완료되었습니다! 재충전하고 내일 만나요!☀️"
            
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
            return False, None

        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")
        return False, None
    
from discord.ext import tasks

# ---------------------------------------- 일일/주간 공부 시간 순위 표시 함수 ----------------------------------------

# 일일 공부 시간 순위 표시 함수 :: 월요일 제외하고 모든 날 일일 순위 보여줌!
@tasks.loop(hours=24)
async def send_daily_study_ranking():
    await client.wait_until_ready()
    if datetime.now(pytz.timezone('Asia/Seoul')).strftime('%A') == 'Monday':
        return  # 월요일은 일일 순위 표시 xxx
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        try:
            # 어제 공부한 멤버들의 공부시간 가져오기
            cursor.execute("""
                SELECT m.member_nickname, SUM(a.log_study_time) AS total_study_time
                FROM activity_log a
                JOIN member m ON a.member_id = m.member_id
                WHERE a.log_date = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                GROUP BY a.member_id
                ORDER BY total_study_time DESC
                LIMIT 10
            """)
            results = cursor.fetchall()

            ranking_message = "======== 일일 공부시간 순위 ========\n"
            for i, (nickname, total_study_time) in enumerate(results, start=1):
                hours, minutes = divmod(total_study_time, 60)
                ranking_message += f"{i}등 {nickname} : {hours}시간 {minutes}분\n"

            if not results:
                ranking_message += "어제는 공부한 멤버가 없습니다.\n"

            ch = client.get_channel(1239098139361808429)
            await ch.send(ranking_message)
        except Error as e:
            print(f"'{e}' 에러 발생")
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# 주간 공부 시간 순위 표시 함수 :: 월요일에만 주간순위 보여줌!
@tasks.loop(hours=168)  # 168 hours = 1 week 이니까.
async def send_weekly_study_ranking():
    await client.wait_until_ready()
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        try:
            # 지난 주에 공부한 멤버들의 공부시간 가져오기
            cursor.execute("""
                SELECT m.member_nickname, SUM(a.log_study_time) AS total_study_time
                FROM activity_log a
                JOIN member m ON a.member_id = m.member_id
                WHERE a.log_date BETWEEN DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) + 7 DAY) AND DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) + 1 DAY)
                GROUP BY a.member_id
                ORDER BY total_study_time DESC
                LIMIT 10
            """)
            results = cursor.fetchall()

            ranking_message = "======== 주간 공부시간 순위 ========\n"
            for i, (nickname, total_study_time) in enumerate(results, start=1):
                hours, minutes = divmod(total_study_time, 60)
                ranking_message += f"{i}등 {nickname} : {hours}시간 {minutes}분\n"

            if not results:
                ranking_message += "지난 주에는 공부한 멤버가 없습니다.\n"

            ch = client.get_channel(1239098139361808429)
            await ch.send(ranking_message)
        except Error as e:
            print(f"'{e}' 에러 발생")
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")
   

# ---------------------------------------- 내 정보 확인 함수 ----------------------------------------

# 공부시간 안내 함수
async def send_study_time_info(user, member_id, period_id):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        try:
            # 오늘 공부시간
            cursor.execute(
                "SELECT log_study_time FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = CURDATE()",
                (member_id, period_id)
            )
            today_study_time = cursor.fetchone()
            if today_study_time:
                today_study_time = today_study_time[0]
            else:
                today_study_time = 0

            # 이번 주 공부시간
            cursor.execute(
                """
                SELECT SUM(log_study_time) FROM activity_log
                WHERE member_id = %s AND period_id = %s
                AND log_date >= DATE_SUB(CURDATE(), INTERVAL WEEKDAY(CURDATE()) DAY)
                AND log_date <= CURDATE()
                """,
                (member_id, period_id)
            )
            week_study_time = cursor.fetchone()
            if week_study_time and week_study_time[0]:
                week_study_time = week_study_time[0]
            else:
                week_study_time = 0

            # 누적 공부시간
            cursor.execute(
                """
                SELECT SUM(log_study_time) FROM activity_log
                WHERE member_id = %s AND period_id = %s
                """,
                (member_id, period_id)
            )
            total_study_time = cursor.fetchone()
            if total_study_time and total_study_time[0]:
                total_study_time = total_study_time[0]
            else:
                total_study_time = 0

            # 시간과 분으로 변환
            today_hours, today_minutes = divmod(today_study_time, 60)
            week_hours, week_minutes = divmod(week_study_time, 60)
            total_hours, total_minutes = divmod(total_study_time, 60)

            await user.send(
                f"현재까지의 공부시간을 알려드릴게요!.\n"
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


# ================================================ 서버 이벤트 ================================================

# intent를 추가하여 봇이 서버의 특정 이벤트를 구독하도록 허용
intents = discord.Intents.default()
intents.messages = True  # 메시지를 읽고 반응하도록
intents.message_content = True  # 메시지 내용에 접근
intents.guilds = True  # 채널
intents.voice_states = True #음성 상태 정보 갱신
intents.members = True  # 멤버 관련 이벤트 처리 활성화

# 봇 클라이언트 설정
client = discord.Client(intents = intents)

# 봇이 실행중일 때 상태메시지
@client.event
async def on_ready():
    print("터미널에서 실행됨")
    await client.change_presence(status=discord.Status.online, activity=discord.Game("공부 안하고 딴짓"))
    check_absences.start()  # 결석체크 함수 예약
    send_daily_study_ranking.start()   # 일일순위 체크 함수 예약
    send_weekly_study_ranking.change_interval(time=datetime.time(hour=0, minute=1))
    send_weekly_study_ranking.start()   # 주간순위 체크 함수 예약
    schedule_midnight_tasks.start()  # 자정 작업 스케줄러 시작
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


# '공지' 명령어 입력 시 공지사항 출력 / '휴가신청' 입력 시 휴가신청 / '공부시간' 입력 시 공부시간 안내
@client.event
async def on_message(message):
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
                cursor = connection.cursor(buffered=True)
                cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(message.author),))
                result = cursor.fetchone()
                if result:
                    member_id = result[0]
                    cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = 1", (member_id,))
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


# 공부 시작 / 공부 종료 함수  -- 오류 해결때문에 각각 로그 추가!
@client.event
async def on_voice_state_update(member, before, after):
    ch = client.get_channel(1239098139361808429)
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
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
            cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = 1", (member_id,))
            result = cursor.fetchone()
            if result:
                period_id = result[0]
            else:
                cursor.close()
                connection.close()
                return  # 활동 기간 정보가 없으면 함수 종료

            cursor.close()
            connection.close() 

            member_display_name = member.display_name

            # 카메라 on 하면 = 공부 시작
            if before.self_video is False and after.self_video is True:
                await ch.send(f"{member_display_name}님 공부 시작!✏️")
                start_study_session(member_id, period_id, member_display_name)
            
            # 카메라 on 상태였다가 카메라 off 또는 음성채널 나갈 경우 = 공부 종료
            elif (before.self_video is True and after.self_video is False) or (before.channel is not None and after.channel is None):
                success, message = await end_study_session(member_id, period_id, member_display_name)
                if success and message:
                    await ch.send(message)  # 공부기록됐다~ 메시지 전송

        except Error as e:
            print(f"'{e}' 에러 발생")
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# 11:59가 되면 공부시간 저장
async def end_study_session_at_midnight(member_id, period_id, member_display_name):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d 23:59:59')
        try:
            # 시작 시간 가져오기
            cursor.execute(
                "SELECT session_start_time FROM study_session WHERE member_id = %s AND period_id = %s ORDER BY session_id DESC LIMIT 1",
                (member_id, period_id)
            )
            start_time_result = cursor.fetchone()
            if start_time_result is None:
                print(f"{member_display_name}님의 시작 시간이 등록되지 않았습니다.")
                return False, None
            start_time = start_time_result[0]
            # 시작 시간이 datetime 객체가 아닌 경우 문자열로 변환
            if isinstance(start_time, str):
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            else:
                start_dt = start_time
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            duration = int((end_dt - start_dt).total_seconds() // 60)
            # 종료 시간 및 기간 업데이트
            cursor.execute(
                "UPDATE study_session SET session_end_time = %s, session_duration = %s WHERE member_id = %s AND period_id = %s AND session_end_time IS NULL",
                (end_time, duration, member_id, period_id)
            )
            connection.commit()
            # 공부 시간이 5분 이상인 경우에만 activity_log 테이블의 log_study_time에 공부시간 누적
            if duration >= 5:
                # activity_log에 해당 날짜와 멤버의 레코드가 존재하는지 확인
                log_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
                cursor.execute(
                    "SELECT log_id FROM activity_log WHERE member_id = %s AND period_id = %s AND log_date = %s",
                    (member_id, period_id, log_date)
                )
                log_id = cursor.fetchone()
                if log_id:
                    # 이미 존재하는 레코드에 공부 시간 누적
                    cursor.execute(
                        "UPDATE activity_log SET log_study_time = log_study_time + %s WHERE log_id = %s",
                        (duration, log_id[0])
                    )
                else:
                    # 새로운 레코드 삽입
                    cursor.execute(
                        "INSERT INTO activity_log (member_id, period_id, log_date, log_study_time) VALUES (%s, %s, %s, %s)",
                        (member_id, period_id, log_date, duration)
                    )
                message = f"{member_display_name}님 {duration}분 동안 공부했습니다!👍"
                print(f"{member_display_name}님의 최근 공부 시간: {duration}분")
            else:
                message = f"{member_display_name}님 공부 시간이 5분 미만이어서 기록되지 않았습니다."
                print(f"{member_display_name}님의 공부 시간이 5분 미만이어서 기록되지 않았습니다.")
            connection.commit()
            return True, message
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()
            return False, None
        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")
        return False, None


# 봇 실행 토큰
client.run(token)
