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
                              timestamp=datetime.now(pytz.timezone('UTC')), color=0x75c3c5)
        embed.add_field(name = "📚 공부는 어떻게 시작하나요?", value= "[study room] 채널에서 카메라를 켜면 공부시간 측정 시작! \n카메라를 끄면 시간 측정이 종료되고, \n일일 공부시간에 누적돼요. \n공부시간 5분 이하는 인정되지 않아요.\n\n", inline=False)
        embed.add_field(name = "⏰매일 5분 이상 공부해야 해요!", value= "이 스터디의 목표는 [꾸준히 공부하는 습관]이에요. \n조금이라도 좋으니 매일매일 공부해보세요!\n", inline=False)
        embed.add_field(name = "✍️ 카메라로 얼굴을 꼭 보여줘야 하나요?", value= "아니요! 공부하는 모습을 부분적으로 보여준다면 다 좋아요. \nex) 공부하는 손, 타이핑하는 키보드, 종이가 넘어가는 책... \n물론 얼굴을 보여준다면 반갑게 인사할게요.\n", inline=False)
        embed.add_field(name = "🛏️쉬고싶은 날이 있나요?", value= "채팅 채널 [휴가신청]에 \"휴가\"라고 남기면 돼요. (주 1회 가능) \n휴가를 제출한 날은 공부한 것으로 인정됩니다.\n", inline=False)
        embed.add_field(name = "⚠️스터디 조건 미달", value= "공부를 하지 않은 날이 3회 누적되는 경우 스터디에서 제외됩니다. \n하지만 언제든 다시 서버에 입장하여 도전할 수 있어요!\n", inline=False)
        embed.add_field(name = "📊공부시간 순위 공개", value= "매일 자정에 일일 공부시간 순위가 공개됩니다.\n매주 월요일 0시에 주간 공부시간 순위가 공개됩니다.\n", inline=False)
        embed.set_footer(text="Bot made by.에옹", icon_url="https://cdn.discordapp.com/attachments/1238886734725648499/1238904212805648455/hamster-apple.png?ex=6640faf6&is=663fa976&hm=7e82b5551ae0bc4f4265c15c1ae0be3ef40ba7aaa621347baf1f46197d087fd6&")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1238886734725648499/1238905277777051738/file-0qJvNUQ1lyaUiZDmuOEI24BT.png?ex=6640fbf3&is=663faa73&hm=f2f65e3623da6c444361aa9938691d152623c88de4ca51852adc47e8b755289d&")
        await message.channel.send(embed=embed)

    if message.content == "휴가신청":  # 휴가신청은 휴가신청방에서만 신청할 수 있도록 해야!
        # [휴가신청]에 메시지 보내기
        ch = client.get_channel(1238896271939338282)
        await ch.send("{} | {}님, 오늘 휴가신청이 완료되었습니다! 재충전하고 내일 만나요☀️".format(message.author, message.author.mention))

# 카메라 on, off시 안내 메시지
@client.event
async def on_voice_state_update(member, before, after):
    ch = client.get_channel(1239098139361808429)

    # if not before.channel and after.channel:  # 채널 입장 시 [공부기록] 채널에 알림
    #    await ch.send(f"{member}님이 [{after.channel}] 채널에 입장했습니다.")
    # elif before.channel and not after.channel:  # 채널 퇴장 시 [공부기록] 채널에 알림
    #    await ch.send(f"{member}님이 [{before.channel}] 채널을 떠났습니다.")

    if before.self_video is False and after.self_video is True:
        await ch.send(f"{member.display_name}님 공부 시작!✏️")  # 카메라 on
    elif before.self_video is True and after.self_video is False:
        await ch.send(f"{member.display_name}님 00분 누적 완료!👍")  # 카메라 off

# 봇을 실행시키기 위한 토큰 작성하는 부분
client.run('MTIzODg4MTY1ODMzODU0MTU3OA.G7Wkj9.P0PmbdQf7MmyTIjdJSfX4JOExa8U-E51-fMCh0')