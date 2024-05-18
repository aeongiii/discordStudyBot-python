import discord
from discord.ext import commands
import asyncio
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import pytz

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
                # 기존 멤버가 있으면 membership_period 테이블에 새로운 기간을 등록
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


# 공부 세션 종료 정보 업데이트
async def end_study_session(member_id, period_id, member_display_name):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)  # 커서를 버퍼링 모드로 설정
        end_time = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S')
        try:
            # 시작 시간 가져오기
            cursor.execute(
                "SELECT session_start_time FROM study_session WHERE member_id = %s AND period_id = %s ORDER BY session_id DESC LIMIT 1",
                (member_id, period_id)
            )
            start_time_result = cursor.fetchone()
            if start_time_result is None:
                print(f"{member_display_name}님의 시작 시간이 없습니다.")
                return False, None
            start_time = start_time_result[0]
            # 시작 시간이 datetime 객체가 아닌 경우 문자열로 변환
            if isinstance(start_time, str):
                start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
            else:
                start_dt = start_time
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
            duration = int((end_dt - start_dt).total_seconds() // 60)
            print(f"start_dt: {start_dt}, end_dt: {end_dt}, duration: {duration}")
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

# 휴가 기록 추가 함수
def insert_vacation_log(member_id, period_id, member_display_name):
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)
        vacation_date = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d')
        vacation_week_start = (datetime.now(pytz.timezone('Asia/Seoul')) - timedelta(days=datetime.now(pytz.timezone('Asia/Seoul')).weekday())).strftime('%Y-%m-%d')

        try:
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
            print(f"{member_display_name}님의 휴가 기록이 추가되었습니다. [날짜 : {vacation_date}]")
            
        except Error as e:
            print(f"'{e}' 에러 발생")
            connection.rollback()

        finally:
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")

# intent를 추가하여 봇이 서버의 특정 이벤트를 구독하도록 허용
intents = discord.Intents.default()
intents.messages = True  # 메시지를 읽고 반응하도록
intents.message_content = True  # 메시지 내용에 접근
intents.guilds = True  # 채널
intents.voice_states = True #음성 상태 정보 갱신
intents.members = True  # 멤버 관련 이벤트 처리 활성화

# 봇 클라이언트 설정
client = discord.Client(intents = intents)

@client.event
async def on_ready() : # 봇이 실행되면 한 번 실행함
    print("터미널에서 실행됨") 
    await client.change_presence(status=discord.Status.online, activity=discord.Game("공부 안하고 딴짓"))

# 멤버 새로 참여 시 [member]와 [membership_period]테이블에 정보 추가
@client.event
async def on_member_join(member):
    print(f'[{member.display_name}]님이 서버에 참여했습니다.')
    insert_member_and_period(member)  

# 공지
@client.event
async def on_message(message):
    if message.content == "공지": # 메시지 감지
        # 채널에 전체공개 메시지 보내기
        # await message.channel.send ("{} | {}님, 오늘도 열공하세요!✏️".format(message.author, message.author.mention))
        
        # 다이렉트 메세지(1:1) 보내기
        # await message.author.send ("{} | {}, User, Hello".format(message.author, message.author.mention))

        # 임베드하여 공지글 출력하기
        embed = discord.Embed(title="아아- 공지채널에서 알립니다.📢", description="{}님, 환영합니다!\n".format(message.author, message.author.mention), 
                              timestamp=datetime.now(pytz.timezone('Asia/Seoul')), color=0x75c3c5)
        embed.add_field(name = "📚 공부는 어떻게 시작하나요?", value= "[study room] 채널에서 카메라를 켜면 공부시간 측정 시작! \n카메라를 끄면 시간 측정이 종료되고, \n일일 공부시간에 누적돼요. \n공부시간 5분 이하는 인정되지 않아요.\n\n", inline=False)
        embed.add_field(name = "⏰매일 5분 이상 공부해야 해요!", value= "이 스터디의 목표는 [꾸준히 공부하는 습관]이에요. \n조금이라도 좋으니 매일매일 공부해보세요!\n", inline=False)
        embed.add_field(name = "✍️ 카메라로 얼굴을 꼭 보여줘야 하나요?", value= "아니요! 공부하는 모습을 부분적으로 보여준다면 다 좋아요. \nex) 공부하는 손, 타이핑하는 키보드, 종이가 넘어가는 책... \n물론 얼굴을 보여준다면 반갑게 인사할게요.\n", inline=False)
        embed.add_field(name = "🛏️쉬고싶은 날이 있나요?", value= "채팅 채널 [휴가신청]에 \"휴가\"라고 남기면 돼요. (주 1회 가능) \n휴가를 사용해도 공부 가능하지만, 휴가를 취소할 수는 없어요. \n휴가를 제출한 날은 공부한 것으로 인정됩니다.\n", inline=False)
        embed.add_field(name = "⚠️스터디 조건 미달", value= "공부를 하지 않은 날이 3회 누적되는 경우 스터디에서 제외됩니다. \n하지만 언제든 다시 서버에 입장하여 도전할 수 있어요!\n", inline=False)
        embed.add_field(name = "📊공부시간 순위 공개", value= "매일 자정에 일일 공부시간 순위가 공개됩니다.\n매주 월요일 0시에 주간 공부시간 순위가 공개됩니다.\n", inline=False)
        embed.set_footer(text="Bot made by.에옹", icon_url="https://cdn.discordapp.com/attachments/1238886734725648499/1238904212805648455/hamster-apple.png?ex=6640faf6&is=663fa976&hm=7e82b5551ae0bc4f4265c15c1ae0be3ef40ba7aaa621347baf1f46197d087fd6&")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1238886734725648499/1238905277777051738/file-0qJvNUQ1lyaUiZDmuOEI24BT.png?ex=6640fbf3&is=663faa73&hm=f2f65e3623da6c444361aa9938691d152623c88de4ca51852adc47e8b755289d&")
        await message.channel.send(embed=embed)

    if message.content == "휴가신청":
        if message.channel.id == 1238896271939338282:
            connection = create_db_connection()
            if connection:
                cursor = connection.cursor(buffered=True)
                cursor.execute("SELECT member_id FROM member WHERE member_username = %s", (str(message.author),))
                result = cursor.fetchone()
                cursor.fetchall()  # 모든 결과를 명시적으로 읽음

                if result:
                    member_id = result[0]
                    cursor.execute("SELECT period_id FROM membership_period WHERE member_id = %s AND period_now_active = 1", (member_id,))
                    result = cursor.fetchone()
                    cursor.fetchall()  # 모든 결과를 명시적으로 읽음

                    if result: 
                        period_id = result[0]
                        insert_vacation_log(member_id, period_id, message.author.display_name)
                        await message.channel.send(f"{message.author.mention}님, 휴가신청 완료! 재충전하고 내일 만나요!☀️")
                    else:
                        await message.channel.send(f"{message.author.mention}님의 활동 기간을 찾을 수 없습니다.")
                else:
                    await message.channel.send(f"{message.author.mention}님의 정보를 찾을 수 없습니다.")
                
                cursor.close()
                connection.close()
            else:
                await message.channel.send("DB 연결 실패")
        else:
            await message.channel.send(f"{message.author.mention}님, 휴가신청은 [휴가신청] 채널에서 부탁드려요!")


# 이미 이번주에 휴가 사용한 경우 안내하기





@client.event
async def on_voice_state_update(member, before, after):
    ch = client.get_channel(1239098139361808429)

    # 멤버 정보와 활동 기간 ID 가져오기
    connection = create_db_connection()
    if connection:
        cursor = connection.cursor(buffered=True)  # 버퍼링 된 커서 사용

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

            if before.self_video is False and after.self_video is True:
                await ch.send(f"{member_display_name}님 공부 시작!✏️")  # 카메라 on
                start_study_session(member_id, period_id, member_display_name)
            elif (before.self_video is True and after.self_video is False) or (before.channel is not None and after.channel is None):
                success, message = await end_study_session(member_id, period_id, member_display_name)
                if success and message:
                    await ch.send(message)  # 카메라 off 후 메시지 전송

        except Error as e:
            print(f"'{e}' 에러 발생")
            cursor.close()
            connection.close()
    else:
        print("DB 연결 실패")





























# 봇 실행 토큰
client.run('MTIzODg4MTY1ODMzODU0MTU3OA.G7Wkj9.P0PmbdQf7MmyTIjdJSfX4JOExa8U-E51-fMCh0')
