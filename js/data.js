/*
 * 샘플 데이터. 모든 병원, 의료진, 주소, 전화번호는 가상의 정보입니다.
 * 나중에 백엔드(FastAPI 등)가 생기면 이 파일 대신 GET /api/clinics 응답을 쓰면 됩니다.
 */
window.SPECIALTIES = {
  eye:     { ko: "눈 성형", en: "Eyes", ja: "目元", zh: "眼部整形" },
  nose:    { ko: "코 성형", en: "Nose", ja: "鼻", zh: "鼻部整形" },
  contour: { ko: "윤곽", en: "Facial contouring", ja: "輪郭", zh: "轮廓" },
  lifting: { ko: "리프팅", en: "Lifting", ja: "リフトアップ", zh: "提拉" },
  breast:  { ko: "가슴", en: "Breast", ja: "バスト", zh: "胸部" },
  skin:    { ko: "피부", en: "Skin", ja: "肌", zh: "皮肤" },
  body:    { ko: "지방흡입", en: "Liposuction", ja: "脂肪吸引", zh: "吸脂" }
};

window.PROCEDURES = {
  doubleEyelid: { ko: "쌍꺼풀", en: "Double eyelid", ja: "二重整形", zh: "双眼皮" },
  ptosis:       { ko: "눈매교정", en: "Ptosis correction", ja: "眼瞼下垂矯正", zh: "上睑下垂矫正" },
  rhinoplasty:  { ko: "코 성형", en: "Rhinoplasty", ja: "鼻整形", zh: "隆鼻" },
  vline:        { ko: "V라인 윤곽", en: "V-line contouring", ja: "Vライン輪郭", zh: "V脸轮廓" },
  threadLift:   { ko: "실 리프팅", en: "Thread lift", ja: "糸リフト", zh: "埋线提拉" },
  facelift:     { ko: "안면거상", en: "Facelift", ja: "フェイスリフト", zh: "拉皮手术" },
  breastAug:    { ko: "가슴 확대", en: "Breast augmentation", ja: "豊胸", zh: "隆胸" },
  laserToning:  { ko: "레이저 토닝", en: "Laser toning", ja: "レーザートーニング", zh: "激光嫩肤" },
  botox:        { ko: "보톡스", en: "Botox", ja: "ボトックス", zh: "肉毒素" },
  filler:       { ko: "필러", en: "Filler", ja: "ヒアルロン酸", zh: "玻尿酸" },
  lipo:         { ko: "지방흡입", en: "Liposuction", ja: "脂肪吸引", zh: "吸脂" },
  consult:      { ko: "일반 상담", en: "General consultation", ja: "一般カウンセリング", zh: "一般咨询" }
};

window.CLINICS = [
  {
    id: "c01",
    name: { ko: "서울하늘 성형외과", en: "Seoul Haneul Plastic Surgery", ja: "ソウルハヌル美容外科", zh: "首尔天空整形外科" },
    area: { ko: "강남구 신사동", en: "Sinsa-dong, Gangnam", ja: "江南区 新沙洞", zh: "江南区 新沙洞" },
    address: { ko: "서울 강남구 도산대로 000 (가상 주소)", en: "000 Dosan-daero, Gangnam-gu, Seoul (fictional)", ja: "ソウル江南区島山大路000（架空）", zh: "首尔江南区岛山大路000号（虚构）" },
    phone: "02-000-0101",
    specialties: ["eye", "nose"],
    about: {
      ko: "자연스러운 눈매와 코 라인을 전문으로 하는 병원입니다. 1:1 상담으로 얼굴 전체의 균형을 고려해 디자인합니다.",
      en: "Specializes in natural-looking eyes and nose lines, designed for overall facial balance through one-on-one consultations.",
      ja: "自然な目元と鼻のラインを専門とするクリニック。1対1のカウンセリングで顔全体のバランスを考えてデザインします。",
      zh: "专注于自然的眼部和鼻部线条，通过一对一咨询，综合考虑整体面部比例进行设计。"
    },
    doctors: [
      { name: { ko: "김하늘 원장", en: "Dr. Haneul Kim", ja: "キム・ハヌル院長", zh: "金天空 院长" } },
      { name: { ko: "이서준 원장", en: "Dr. Seojun Lee", ja: "イ・ソジュン院長", zh: "李瑞俊 院长" } }
    ],
    procedures: [ { key: "doubleEyelid", price: 1200000 }, { key: "ptosis", price: 1800000 }, { key: "rhinoplasty", price: 3500000 } ],
    hours: { open: "10:00", close: "19:00" },
    closedDays: [0],
    hue: 340,
    seed: { sum: 4.7 * 128, count: 128 },
    reviews: [
      { nick: "minji", rating: 5, text: { ko: "상담이 정말 친절했어요.", en: "Very kind consultation.", ja: "カウンセリングがとても親切でした。", zh: "咨询非常亲切。" } },
      { nick: "jh_park", rating: 4, text: { ko: "대기 시간이 조금 길었지만 만족해요.", en: "A bit of a wait, but happy with it.", ja: "待ち時間は少し長かったけど満足です。", zh: "等待时间稍长，但很满意。" } }
    ]
  },
  {
    id: "c02",
    name: { ko: "라인앤핏 성형외과", en: "Line & Fit Plastic Surgery", ja: "ライン＆フィット美容外科", zh: "线条与契合整形外科" },
    area: { ko: "강남구 압구정동", en: "Apgujeong, Gangnam", ja: "江南区 狎鴎亭洞", zh: "江南区 狎鸥亭洞" },
    address: { ko: "서울 강남구 압구정로 000 (가상 주소)", en: "000 Apgujeong-ro, Gangnam-gu, Seoul (fictional)", ja: "ソウル江南区狎鴎亭路000（架空）", zh: "首尔江南区狎鸥亭路000号（虚构）" },
    phone: "02-000-0202",
    specialties: ["contour", "lifting"],
    about: {
      ko: "윤곽 수술과 리프팅을 함께 설계하는 얼굴 라인 전문 병원입니다. 3D CT로 사전 시뮬레이션을 제공합니다.",
      en: "A facial-line clinic that plans contouring and lifting together, with 3D CT simulation before surgery.",
      ja: "輪郭手術とリフトアップを組み合わせて設計するフェイスライン専門クリニック。3D CTで事前シミュレーションを行います。",
      zh: "将轮廓手术与提拉结合设计的脸型专科医院，术前提供3D CT模拟。"
    },
    doctors: [ { name: { ko: "박도윤 원장", en: "Dr. Doyun Park", ja: "パク・ドユン院長", zh: "朴道允 院长" } } ],
    procedures: [ { key: "vline", price: 9000000 }, { key: "threadLift", price: 1500000 }, { key: "facelift", price: 8000000 } ],
    hours: { open: "09:30", close: "18:30" },
    closedDays: [0, 1],
    hue: 210,
    seed: { sum: 4.5 * 86, count: 86 },
    reviews: [
      { nick: "sora", rating: 5, text: { ko: "시뮬레이션 덕분에 결과를 미리 알 수 있었어요.", en: "The simulation helped me picture the result.", ja: "シミュレーションで結果がイメージできました。", zh: "模拟让我提前看到了效果。" } }
    ]
  },
  {
    id: "c03",
    name: { ko: "봄빛 성형외과", en: "Bombit Plastic Surgery", ja: "ボムビッ美容外科", zh: "春光整形外科" },
    area: { ko: "서초구 반포동", en: "Banpo, Seocho", ja: "瑞草区 盤浦洞", zh: "瑞草区 盘浦洞" },
    address: { ko: "서울 서초구 신반포로 000 (가상 주소)", en: "000 Sinbanpo-ro, Seocho-gu, Seoul (fictional)", ja: "ソウル瑞草区新盤浦路000（架空）", zh: "首尔瑞草区新盘浦路000号（虚构）" },
    phone: "02-000-0303",
    specialties: ["skin", "lifting"],
    about: {
      ko: "수술 없이 받을 수 있는 피부·안티에이징 시술 중심의 병원입니다. 점심시간 시술도 가능합니다.",
      en: "Focused on non-surgical skin and anti-aging treatments. Lunch-break appointments available.",
      ja: "手術なしで受けられる肌・アンチエイジング施術が中心。昼休みの施術も可能です。",
      zh: "以非手术皮肤与抗衰老项目为主，午休时间也可接受治疗。"
    },
    doctors: [ { name: { ko: "최유나 원장", en: "Dr. Yuna Choi", ja: "チェ・ユナ院長", zh: "崔有娜 院长" } } ],
    procedures: [ { key: "laserToning", price: 100000 }, { key: "botox", price: 50000 }, { key: "filler", price: 250000 }, { key: "threadLift", price: 1200000 } ],
    hours: { open: "10:00", close: "20:00" },
    closedDays: [0],
    hue: 30,
    seed: { sum: 4.8 * 214, count: 214 },
    reviews: [
      { nick: "yuki", rating: 5, text: { ko: "통역 도움을 받아 편했어요.", en: "Interpreter support made it easy.", ja: "通訳サポートがあって安心でした。", zh: "有翻译协助，很方便。" } },
      { nick: "dana", rating: 5, text: { ko: "피부톤이 확실히 밝아졌어요.", en: "My skin tone is clearly brighter.", ja: "肌のトーンが明るくなりました。", zh: "肤色明显提亮了。" } }
    ]
  },
  {
    id: "c04",
    name: { ko: "더바디 성형외과", en: "The Body Plastic Surgery", ja: "ザ・ボディ美容外科", zh: "塑身整形外科" },
    area: { ko: "강남구 역삼동", en: "Yeoksam, Gangnam", ja: "江南区 駅三洞", zh: "江南区 驿三洞" },
    address: { ko: "서울 강남구 테헤란로 000 (가상 주소)", en: "000 Teheran-ro, Gangnam-gu, Seoul (fictional)", ja: "ソウル江南区テヘラン路000（架空）", zh: "首尔江南区德黑兰路000号（虚构）" },
    phone: "02-000-0404",
    specialties: ["breast", "body"],
    about: {
      ko: "가슴 성형과 지방흡입을 전문으로 하며, 마취과 전문의가 상주합니다.",
      en: "Specializes in breast surgery and liposuction, with a resident anesthesiologist.",
      ja: "豊胸と脂肪吸引が専門。麻酔科専門医が常駐しています。",
      zh: "专注于胸部整形与吸脂，麻醉科专科医生常驻。"
    },
    doctors: [
      { name: { ko: "정민호 원장", en: "Dr. Minho Jung", ja: "チョン・ミンホ院長", zh: "郑敏浩 院长" } },
      { name: { ko: "한지우 원장", en: "Dr. Jiwoo Han", ja: "ハン・ジウ院長", zh: "韩智宇 院长" } }
    ],
    procedures: [ { key: "breastAug", price: 7000000 }, { key: "lipo", price: 3000000 } ],
    hours: { open: "10:00", close: "19:00" },
    closedDays: [0],
    hue: 160,
    seed: { sum: 4.3 * 57, count: 57 },
    reviews: [
      { nick: "eun", rating: 4, text: { ko: "사후 관리가 꼼꼼해요.", en: "Thorough aftercare.", ja: "アフターケアが丁寧です。", zh: "术后护理很细致。" } }
    ]
  },
  {
    id: "c05",
    name: { ko: "미소담 성형외과", en: "Misodam Plastic Surgery", ja: "ミソダム美容外科", zh: "微笑整形外科" },
    area: { ko: "마포구 홍대입구", en: "Hongdae, Mapo", ja: "麻浦区 弘大入口", zh: "麻浦区 弘大入口" },
    address: { ko: "서울 마포구 양화로 000 (가상 주소)", en: "000 Yanghwa-ro, Mapo-gu, Seoul (fictional)", ja: "ソウル麻浦区楊花路000（架空）", zh: "首尔麻浦区杨花路000号（虚构）" },
    phone: "02-000-0505",
    specialties: ["eye", "skin"],
    about: {
      ko: "학생과 직장인을 위한 합리적인 가격의 눈 성형·쁘띠 시술 병원입니다. 저녁 9시까지 진료합니다.",
      en: "Affordable eye surgery and petit procedures for students and office workers. Open until 9 pm.",
      ja: "学生・会社員向けのリーズナブルな目元整形・プチ整形クリニック。夜9時まで診療。",
      zh: "面向学生和上班族的平价眼部整形及微整形医院，营业至晚上9点。"
    },
    doctors: [ { name: { ko: "윤소희 원장", en: "Dr. Sohee Yoon", ja: "ユン・ソヒ院長", zh: "尹素熙 院长" } } ],
    procedures: [ { key: "doubleEyelid", price: 900000 }, { key: "botox", price: 30000 }, { key: "filler", price: 190000 } ],
    hours: { open: "12:00", close: "21:00" },
    closedDays: [3],
    hue: 280,
    seed: { sum: 4.4 * 163, count: 163 },
    reviews: [
      { nick: "chen", rating: 4, text: { ko: "가격 대비 만족스러워요.", en: "Great value for money.", ja: "コスパが良いです。", zh: "性价比很高。" } }
    ]
  },
  {
    id: "c06",
    name: { ko: "노블 리프팅 클리닉", en: "Noble Lifting Clinic", ja: "ノーブル・リフティング・クリニック", zh: "贵族提拉诊所" },
    area: { ko: "강남구 청담동", en: "Cheongdam, Gangnam", ja: "江南区 清潭洞", zh: "江南区 清潭洞" },
    address: { ko: "서울 강남구 청담동 000 (가상 주소)", en: "000 Cheongdam-dong, Gangnam-gu, Seoul (fictional)", ja: "ソウル江南区清潭洞000（架空）", zh: "首尔江南区清潭洞000号（虚构）" },
    phone: "02-000-0606",
    specialties: ["lifting", "skin"],
    about: {
      ko: "40대 이상을 위한 안면거상·리프팅 전문 클리닉입니다. 회복 기간을 줄이는 맞춤 플랜을 제안합니다.",
      en: "Facelift and lifting specialists for patients 40+, with plans tailored to shorten recovery.",
      ja: "40代以上向けのフェイスリフト・リフトアップ専門クリニック。ダウンタイムを抑えたプランを提案します。",
      zh: "面向40岁以上人群的拉皮与提拉专科诊所，提供缩短恢复期的定制方案。"
    },
    doctors: [ { name: { ko: "강태오 원장", en: "Dr. Taeo Kang", ja: "カン・テオ院長", zh: "姜泰吾 院长" } } ],
    procedures: [ { key: "facelift", price: 9500000 }, { key: "threadLift", price: 1800000 }, { key: "botox", price: 80000 } ],
    hours: { open: "10:00", close: "18:00" },
    closedDays: [0, 6],
    hue: 45,
    seed: { sum: 4.6 * 74, count: 74 },
    reviews: []
  },
  {
    id: "c07",
    name: { ko: "코어 코 성형외과", en: "Core Rhinoplasty Clinic", ja: "コア鼻整形クリニック", zh: "核心鼻整形外科" },
    area: { ko: "강남구 논현동", en: "Nonhyeon, Gangnam", ja: "江南区 論峴洞", zh: "江南区 论岘洞" },
    address: { ko: "서울 강남구 논현로 000 (가상 주소)", en: "000 Nonhyeon-ro, Gangnam-gu, Seoul (fictional)", ja: "ソウル江南区論峴路000（架空）", zh: "首尔江南区论岘路000号（虚构）" },
    phone: "02-000-0707",
    specialties: ["nose"],
    about: {
      ko: "코 성형 단일 진료 병원으로, 재수술과 기능 개선(비중격) 수술까지 함께 다룹니다.",
      en: "A nose-only clinic that also handles revision and functional (septum) surgery.",
      ja: "鼻整形のみを扱うクリニック。再手術や機能改善（鼻中隔）手術にも対応。",
      zh: "专做鼻整形的医院，也提供修复手术和功能性（鼻中隔）手术。"
    },
    doctors: [ { name: { ko: "오지훈 원장", en: "Dr. Jihoon Oh", ja: "オ・ジフン院長", zh: "吴智勋 院长" } } ],
    procedures: [ { key: "rhinoplasty", price: 4000000 }, { key: "filler", price: 300000 } ],
    hours: { open: "10:00", close: "19:00" },
    closedDays: [0],
    hue: 190,
    seed: { sum: 4.9 * 41, count: 41 },
    reviews: [
      { nick: "rin", rating: 5, text: { ko: "재수술이었는데 결과가 아주 좋아요.", en: "It was a revision and the result is great.", ja: "再手術でしたが、とても良い結果です。", zh: "是修复手术，效果非常好。" } }
    ]
  },
  {
    id: "c08",
    name: { ko: "해운대 블룸 성형외과", en: "Haeundae Bloom Plastic Surgery", ja: "海雲台ブルーム美容外科", zh: "海云台绽放整形外科" },
    area: { ko: "부산 해운대구", en: "Haeundae, Busan", ja: "釜山 海雲台区", zh: "釜山 海云台区" },
    address: { ko: "부산 해운대구 해운대로 000 (가상 주소)", en: "000 Haeundae-ro, Haeundae-gu, Busan (fictional)", ja: "釜山海雲台区海雲台路000（架空）", zh: "釜山海云台区海云台路000号（虚构）" },
    phone: "051-000-0808",
    specialties: ["eye", "nose", "contour"],
    about: {
      ko: "부산 지역 종합 성형외과입니다. 해외 환자를 위한 영어·일본어·중국어 상담을 지원합니다.",
      en: "A full-service clinic in Busan with English, Japanese and Chinese consultations for international patients.",
      ja: "釜山の総合美容外科。海外の方向けに英語・日本語・中国語でのカウンセリングに対応。",
      zh: "釜山综合整形外科，为海外患者提供英语、日语、中文咨询。"
    },
    doctors: [
      { name: { ko: "서은비 원장", en: "Dr. Eunbi Seo", ja: "ソ・ウンビ院長", zh: "徐恩菲 院长" } },
      { name: { ko: "임재현 원장", en: "Dr. Jaehyun Lim", ja: "イム・ジェヒョン院長", zh: "林在贤 院长" } }
    ],
    procedures: [ { key: "doubleEyelid", price: 1100000 }, { key: "rhinoplasty", price: 3200000 }, { key: "vline", price: 8500000 } ],
    hours: { open: "09:00", close: "18:00" },
    closedDays: [0],
    hue: 120,
    seed: { sum: 4.2 * 95, count: 95 },
    reviews: [
      { nick: "wang", rating: 4, text: { ko: "중국어 상담이 가능해서 좋았어요.", en: "Glad they offered Chinese consultation.", ja: "中国語で相談できて良かったです。", zh: "可以用中文咨询，很好。" } }
    ]
  }
];
