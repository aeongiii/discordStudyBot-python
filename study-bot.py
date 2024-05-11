import discord, asyncio, datetime, pytz

# intent를 추가하여 봇이 서버의 특정 이벤트를 구독하도록 허용
intents = discord.Intents.default()
intents.messages = True  # 메시지를 읽고 반응하도록
intents.message_content = True  # 메시지 내용에 접근

client = discord.Client(intents = intents)

@client.event
async def on_ready() : # 봇이 실행되면 한 번 실행함
    print("터미널에서 실행됨")
    await client.change_presence(status=discord.Status.online, activity=discord.Game("봇의 상태메시지"))

@client.event
async def on_message(message):
    if message.content == "공지": # 메시지 감지
        # 채널에 전체공개 메시지 보내기
        # await message.channel.send ("{} | {}님, 오늘도 열공하세요!✏️".format(message.author, message.author.mention))
        
        # 다이렉트 메세지(1:1) 보내기
        # await message.author.send ("{} | {}, User, Hello".format(message.author, message.author.mention))

        # 임베드하여 공지글 출력하기
        embed = discord.Embed(title="아아- 공지채널에서 알립니다.📢", description="처음 들어오신 {}님, 환영합니다!".format(message.author, message.author.mention), 
                              timestamp=datetime.datetime.now(pytz.timezone('UTC')), color=0x75c3c5)
        embed.add_field(name = "임베드 라인 1 : inline = false로 책정", value= "라인 이름에 해당하는 값", inline=False)
        embed.add_field(name = "임베드 라인 2 : inline = false로 책정", value= "라인 이름에 해당하는 값", inline=False)
        embed.add_field(name = "임베드 라인 3 : inline = true로 책정", value= "라인 이름에 해당하는 값", inline=True)
        embed.add_field(name = "임베드 라인 4 : inline = true로 책정", value= "라인 이름에 해당하는 값", inline=True)
        embed.set_footer(text="Bot made by.에옹", icon_url="https://cdn.discordapp.com/attachments/1238886734725648499/1238904212805648455/hamster-apple.png?ex=6640faf6&is=663fa976&hm=7e82b5551ae0bc4f4265c15c1ae0be3ef40ba7aaa621347baf1f46197d087fd6&")
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/1238886734725648499/1238905277777051738/file-0qJvNUQ1lyaUiZDmuOEI24BT.png?ex=6640fbf3&is=663faa73&hm=f2f65e3623da6c444361aa9938691d152623c88de4ca51852adc47e8b755289d&")
        await message.channel.send(embed=embed)


    if message.content == "휴가신청":  # 휴가신청은 휴가신청방에서만 신청할 수 있도록 해야!
        # [휴가신청]에 메시지 보내기
        ch = client.get_channel(1238896271939338282)
        await ch.send("{} | {}님, 오늘 휴가신청이 완료되었습니다! 재충전하고 내일 만나요☀️".format(message.author, message.author.mention))




# 봇을 실행시키기 위한 토큰 작성하는 부분
client.run('MTIzODg4MTY1ODMzODU0MTU3OA.G7Wkj9.P0PmbdQf7MmyTIjdJSfX4JOExa8U-E51-fMCh0')