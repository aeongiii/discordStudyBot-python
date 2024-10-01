<img src= "https://capsule-render.vercel.app/api?type=waving&height=300&color=gradient&text=공부시간%20관리%20시스템&desc=Discord%20Bot%20and%20Web%20Dashboard%20for%20Efficient%20Study%20Tracking&descAlign=50&descAlignY=65&descSize=20.1&fontSize=60&section=header&reversal=true&textBg=false&animation=fadeIn&fontAlign=50&fontAlignY=35" />



# 💻 프로젝트 목표
- 디스코드 서버에서 공부 시간을 집계하고 관리할 수 있는 봇을 개발하여 사용자들의 학습 효율성 증대
- 일일 및 주간 공부 시간 집계, 매일 자정에 공부 순위를 공개함으로써 학습 동기 부여
- 3회 이상의 결석 시 경고와 자동 퇴출 기능으로 규칙적인 공부 습관에 도움
- 스프링부트를 활용하여 웹 페이지를 통해 사용자가 학습 데이터를 시각적으로 확인할 수 있도록 기능 확장 중


# 📆 개발 기간
2024.04 ~ 진행 


# 📚 프로젝트 설명
- Python과 Discord API를 사용하여 디스코드 서버 내에서 공부 시간을 관리하는 봇을 개발하였습니다.
- PostgreSQL 데이터베이스를 사용하여 공부 세션을 기록하고 관리합니다.
- 휴가 신청, 결석 체크, 자동 경고 및 퇴출 기능을 통해 개인별 출석 현황 및 공부 시간을 관리합니다.
- 각 사용자의 개인별 학습 통계 및 학습 패턴을 분석하고, 분석 결과를 바탕으로 학습 동기 부여 안내 메시지를 제공합니다.
- APScheduler를 활용하여 매일 자정과 매주 주간 단위로 공부 시간 순위를 갱신합니다.
- Springboot를 통해 웹 대시보드를 제공하여 공부 데이터를 시각화하는 작업을 진행 중입니다.


# 🛠 기술 스택 & 개발 환경
**Backend** | <img src="https://img.shields.io/badge/java-007396?style=for-the-badge&logo=java&logoColor=white"> <img src="https://img.shields.io/badge/springboot-6DB33F?style=for-the-badge&logo=spring&logoColor=white"> <img src="https://img.shields.io/badge/python-3776AB?style=for-the-badge&logo=python&logoColor=white"> 

**Frontend** | <img src="https://img.shields.io/badge/html5-E34F26?style=for-the-badge&logo=html5&logoColor=white"> <img src="https://img.shields.io/badge/javascript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black"> <img src="https://img.shields.io/badge/css-1572B6?style=for-the-badge&logo=css3&logoColor=white"> <img src="https://img.shields.io/badge/bootstrap-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white">

**Database** | <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">

**Tools** | <img src="https://img.shields.io/badge/github-181717?style=for-the-badge&logo=github&logoColor=white"> <img src="https://img.shields.io/badge/git-F05032?style=for-the-badge&logo=git&logoColor=white"> <img src="https://img.shields.io/badge/notion-000000?style=for-the-badge&logo=notion&logoColor=white">

**Server** | <img src="https://img.shields.io/badge/Heroku-430098?style=for-the-badge&logo=heroku&logoColor=white">


# ⚙ 주요 기능
- 공부 세션 관리: 음성 채널에서 카메라를 켜면 공부 시작, 끄면 자동으로 공부 시간 기록하고 안내합니다.
- 일일/주간 공부 시간 순위: 매일 자정에 일일 공부 시간 순위를, 매주 일요일 자정에 주간 순위를 Discord 채널에 공지합니다.
- 결석 관리 및 자동 퇴출: 3회 결석한 사용자에게 개인 알림을 보내고, 자동으로 서버에서 퇴출합니다. 언제든 다시 도전할 수 있습니다.
- 휴가 신청: 휴가를 신청한 사용자는 해당 날짜에 결석 처리되지 않습니다.
  

# 📊 향후 계획
- 웹 대시보드 및 데이터 시각화: Spring Boot와 PostgreSQL을 연동해 학습 데이터를 시각화하여 제공하는 웹 대시보드를 개발 중입니다.
- 개인별 학습 패턴 분석: 개인별 학습 패턴을 분석해 맞춤형 학습 피드백을 제공하는 기능을 추가할 예정입니다.

<img src="https://capsule-render.vercel.app/api?type=waving&color=timeAuto&height=150&section=footer" /> 
