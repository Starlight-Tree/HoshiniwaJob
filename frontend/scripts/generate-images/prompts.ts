export type ImageSpec = {
  id: string
  purpose: string
  prompt: string
  aspectRatio: '16:9'
  imageSize: '1K'
  outputFileName: string
}

// 全画像に共通の世界観。個別の prompt の後ろに足す。
const WORLD =
  'Consistent visual world: a future greenhouse in an orbital botanical garden where plants and technology coexist. ' +
  'Soft natural light, warm, trustworthy, optimistic, realistic photographic texture, restrained sci-fi without flashy effects. ' +
  'No text, no letters, no logos, no real brands, no real facilities, no real people.'

// 求人ごとの画像（仕事中の人物が主役）に共通の末尾。人物は架空で、文字・ロゴ・名札は入れない。
const WORK_TAIL =
  'Candid mid-task moment, natural gestures, nobody looks at the camera, no posed group shot. ' +
  'Eye-level, medium-distance composition, close enough to clearly see the hands and the task; the worker is the primary subject, with the figure occupying roughly half the image height. ' +
  'Photorealistic, restrained sci-fi, soft natural light, calm trustworthy atmosphere. ' +
  'All people are entirely fictional and do not resemble any real person. ' +
  'No text, no letters, no logos, no name tags, no real brands, no real facilities, and nothing readable on any screen, dial, label or sign.'

export const IMAGES: ImageSpec[] = [
  {
    id: 'top-hero',
    purpose: 'トップページのヒーロー画像',
    prompt:
      'A wide 16:9 cinematic photograph of a serene future greenhouse inside an orbital botanical garden. ' +
      'Lush green plants grow in clean white modular planters, with soft natural sunlight and a distant view of Earth through large windows. ' +
      'Warm, trustworthy, optimistic atmosphere. Photorealistic, high detail, no text, no logos, no people. ' +
      WORLD,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'top-hero.png',
  },
  {
    id: 'job-detail-sample',
    purpose: '求人詳細ページの雰囲気画像',
    prompt:
      'A wide 16:9 cinematic photograph of a serene future greenhouse inside an orbital botanical garden. ' +
      'Lush green plants grow in clean white modular planters, with soft natural sunlight and a distant view of Earth through large windows. ' +
      'Warm, trustworthy, optimistic atmosphere. Photorealistic, high detail, no text, no logos, no people. ' +
      WORLD,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'job-detail-sample.png',
  },
  {
    id: 'garden-banner-sample',
    purpose: '園ごとのバナー画像',
    prompt:
      'A wide 16:9 photograph of a beautiful greenhouse garden with rows of healthy plants, soft morning light, and a clean futuristic but friendly atmosphere. ' +
      'Suitable as a banner image for an employer profile. Photorealistic, no text, no logos, no people. ' +
      WORLD,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'garden-banner-sample.png',
  },
  {
    id: 'recruit-7',
    purpose: '求人 ID 7「遺跡前の語り部」（遺跡前ガーデン）の詳細ページ画像',
    prompt:
      'A wide 16:9 photograph of a quiet open-air plaza in front of ancient stone ruins on a future orbital botanical garden. ' +
      'Weathered pale stone arches and low walls, with green ferns, moss and climbing vines growing through them. ' +
      'Rock walls of a cavern-like greenhouse rise in the background, and a narrow tunnel-rail platform is visible in the distance. ' +
      'A small circle of simple wooden benches faces the ruins, as a place where a storyteller would gather visitors. ' +
      'Soft warm afternoon light, calm, trustworthy, curious atmosphere. Photorealistic, restrained sci-fi, no flashy effects. ' +
      'No text, no letters, no logos, no real brands, no real facilities, no real people. No people at all.',
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/7.png',
  },
  {
    // 業務内容はダミーの 1 行だけなので、案内する場面は職種名「遺跡前の語り部」からの演出（求人の記載ではない）。
    id: 'recruit-7-people',
    purpose: '求人 ID 7「遺跡前の語り部」の人物ありの別案（recruit-7 と比較する。ページにはまだ繋がない）',
    prompt:
      'A 16:9 documentary-style photograph of a calm guided talk in front of ancient stone ruins inside an orbital botanical garden. ' +
      'One fictional adult staff member in a simple dark-green work jacket stands beside a weathered stone arch, gesturing with an open hand toward the carvings while explaining. ' +
      'Three fictional visitors in everyday clothes stand a few steps away, listening attentively, one looking at the arch and another tilting their head. ' +
      'Candid mid-conversation moment, natural gestures, nobody looks at the camera, no posed group shot. ' +
      "Eye-level, medium-distance composition, close enough to clearly see the guide's expression and explaining gesture. " +
      'The guide and visitors are the primary subjects, with their figures occupying roughly half the image height. ' +
      'Keep the stone arch and plants clearly recognizable behind them. Do not use a distant architectural establishing shot. ' +
      'Ruins, ferns, moss and climbing vines fill the background; the greenhouse glass ceiling is only a soft, minor element at the top edge and does not dominate. ' +
      'Soft warm afternoon light, calm, trustworthy atmosphere. Photorealistic, restrained sci-fi. ' +
      'All people are entirely fictional and do not resemble any real person. ' +
      'No text, no letters, no logos, no name tags, no real brands, no real facilities.',
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/7-people.png',
  },
  // 以下の recruit-N は求人 ID N 用。業務内容はダミーの 1 行だけなので、場面は職種名からの演出（求人の記載ではない）。
  {
    id: 'recruit-1',
    purpose: '求人 ID 1「無重力蔓の育成士」（環軌道植物公社）',
    prompt:
      'A 16:9 documentary-style photograph inside a bright orbital greenhouse ring. ' +
      'One fictional woman in her thirties with short black hair and a simple dark-green work jacket gently guides long leafy vines that float and curl in microgravity along a lattice, holding one tendril between her fingers and leaning in to check it. ' +
      'Planters and a curved window are visible behind her. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/1.png',
  },
  {
    id: 'recruit-5',
    purpose: '求人 ID 5「酸素供給装置の保守員」（ザーハード砂漠温室組合）',
    prompt:
      'A 16:9 documentary-style photograph inside a desert dome greenhouse. ' +
      'One fictional bearded man in his forties wearing a practical sand-colored work suit kneels at an open access panel of an oxygen-supply unit beside plant beds, reading an analog needle gauge with an unmarked dial and a simple row of green status lights. ' +
      'Sand dunes are visible through the dome glass behind him. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/5.png',
  },
  {
    id: 'recruit-8',
    purpose: '求人 ID 8「遺跡周辺の土壌の調査員」（遺跡前ガーデン）',
    prompt:
      'A 16:9 documentary-style photograph beside a mossy stone ruin wall in an orbital botanical garden. ' +
      'One fictional woman in her fifties with grey hair tied back and a light work vest crouches and takes a soil sample with a small trowel into a clear sample tube. ' +
      'Ferns, moss and weathered stones surround her. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/8.png',
  },
  {
    id: 'recruit-10',
    purpose: '求人 ID 10「種子の記録係」（星庭財団）',
    prompt:
      'A 16:9 documentary-style photograph in a bright seed storage room. ' +
      'One fictional young man in his twenties with round glasses and a plain apron sits at a workbench, examining a tray of seeds through a handheld magnifier while recording what he sees on a tablet placed beside the tray; the tablet is angled away so its screen is not readable. ' +
      'Shelves of glass jars of seeds are behind him. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/10.png',
  },
  {
    id: 'recruit-11',
    purpose: '求人 ID 11「持ち込み植物の検疫官」（静止軌道ガーデンズ）',
    prompt:
      'A 16:9 documentary-style photograph at a plant inspection counter in an orbital station. ' +
      'One fictional woman in her forties with her hair in a bun, wearing a white coat and gloves, examines a leafy plant on the counter with tweezers, a sealed transparent inspection box beside it. ' +
      'A fictional traveler with a travel bag waits patiently in the soft-focus background. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/11.png',
  },
  {
    id: 'recruit-2',
    purpose: '求人 ID 2「人工夜の温室管理員」（環軌道植物公社）',
    prompt:
      'A 16:9 documentary-style photograph inside an orbital greenhouse during its artificial night, with a calm blue-violet atmosphere that is still bright enough for her face, hands and the control panel to be clearly visible, and plants softly illuminated. ' +
      'One fictional woman in her twenties with a long braid and a quilted work vest turns a large unmarked dial on a wall-mounted lighting control panel with one hand while looking over her shoulder at the rows of plants behind her. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/2.png',
  },
  {
    id: 'recruit-3',
    purpose: '求人 ID 3「植物園の語り部」（ミルフェン月面植物園）',
    prompt:
      'A 16:9 documentary-style photograph inside a lunar botanical garden, with a grey lunar landscape and a distant Earth visible through a large window. ' +
      'One fictional man in his sixties with white hair and a light-blue jacket holds up a small potted plant with both hands and explains it to two fictional adult visitors who lean in with interest. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/3.png',
  },
  {
    id: 'recruit-4',
    purpose: '求人 ID 4「夜の花見ガイド」（ミルフェン月面植物園）',
    prompt:
      'A 16:9 documentary-style photograph of a night blossom-viewing walk in a lunar botanical garden, with softly glowing flowering trees along a stone path. ' +
      'The warm light of the lantern and the glowing blossoms keeps the faces, hands and gestures of everyone clearly visible; the scene is not dark. ' +
      'One fictional woman in her thirties in a dark coat holds a warm paper lantern in one hand and points with the other toward the glowing blossoms, leading two fictional adult visitors who follow and look up. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/4.png',
  },
  {
    id: 'recruit-6',
    purpose: '求人 ID 6「砂丘の高機動車の運転案内」（ザーハード砂漠温室組合）',
    prompt:
      'A 16:9 documentary-style photograph at the edge of a desert dome greenhouse, with large sand dunes outside. ' +
      'One fictional man in his thirties with sunglasses pushed up on his forehead and a sand-colored jacket stands beside an open-top all-terrain vehicle, gesturing toward the dunes as he explains the route to a fictional adult passenger sitting in the vehicle. ' +
      'The vehicle carries no markings or lettering. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/6.png',
  },
  {
    id: 'recruit-9',
    purpose: '求人 ID 9「重力別の交配調整員」（星庭財団）',
    prompt:
      'A 16:9 documentary-style close-medium photograph of a plant breeder at work in a laboratory. ' +
      'One fictional woman in her fifties with short curly hair, a lab coat and safety glasses uses a fine brush to carry pollen from one small flower to another, her hands and the brush tip sharp and clearly the focus of the image, her face concentrated. ' +
      'Behind her, two transparent growth chambers side by side, one on a slowly rotating arm, stay soft and out of focus as background only. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/9.png',
  },
  // 以下は開発用ダミーの拡充（標準案）の新規画像。求人の ID・園は未確定なので、ファイル名は ID ではなく職種の slug にしている（求人の記載ではなく、職種名からの演出）。
  {
    id: 'vine-grower-2',
    purpose: '「無重力蔓の育成士」（求人 ID 1）の 2 枚目。人のいない環境の写真',
    prompt:
      'A wide 16:9 photograph of the inside of a bright ring-shaped orbital greenhouse corridor, seen from eye level. ' +
      'Long leafy green vines float and curl in microgravity along a white lattice that follows the curve of the corridor, with clean planters below and a large curved window showing a distant Earth. ' +
      'Soft natural light, calm, trustworthy, optimistic atmosphere. Photorealistic, restrained sci-fi, no flashy effects. ' +
      'No people at all. No text, no letters, no logos, no real brands, no real facilities, and nothing readable on any screen, dial, label or sign.',
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/1-2.png',
  },
  {
    id: 'plant-doctor-1',
    purpose: '植物医（新規求人・3 枚中の 1 枚目。ヒーロー）',
    prompt:
      'A 16:9 documentary-style photograph in a bright plant clinic room inside an orbital botanical garden. ' +
      'One fictional man in his forties with short grey-streaked hair and a white coat holds a small potted plant under a desk lamp and studies a spotted leaf through a hand magnifier, his brow slightly furrowed in concentration. ' +
      'Other potted plants wait on shelves behind him, a few with small blank paper tags. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/plant-doctor.png',
  },
  {
    id: 'plant-doctor-2',
    purpose: '植物医（新規求人・3 枚中の 2 枚目）',
    prompt:
      'A 16:9 documentary-style photograph of a treatment bench in a plant clinic aboard an orbital botanical garden. ' +
      'One fictional woman in her thirties with shoulder-length hair, a white coat and gloves carefully places a drop of clear liquid from a dropper onto a seedling inside an open transparent treatment cabinet, her face calm and focused. ' +
      'Rows of healthy small seedlings in trays are softly visible behind her. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/plant-doctor-2.png',
  },
  {
    id: 'plant-doctor-3',
    purpose: '植物医（新規求人・3 枚中の 3 枚目。手元のアップ）',
    prompt:
      'A 16:9 close-up documentary-style photograph of two gloved hands holding one spotted, wilting leaf and one healthy green leaf side by side to compare them, above a clean white examination tray. ' +
      'Only the hands, forearms and a white coat sleeve are visible; no faces. A blurred greenhouse with plants is in the background. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/plant-doctor-3.png',
  },
  {
    id: 'garden-pr-photographer',
    purpose: '広報担当（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph inside a greenhouse of an orbital botanical garden. ' +
      'One fictional woman in her thirties with a short bob and a casual green jacket crouches low and photographs a softly glowing night-blooming flower with a mirrorless camera, her eye pressed to the viewfinder; a small reflector panel stands beside her. ' +
      'Rows of flowering plants fill the background. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/garden-pr.png',
  },
  {
    id: 'entrance-receptionist',
    purpose: '入園受付（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph of a bright, airy entrance hall of an orbital botanical garden with a curved wooden reception counter and hanging plants. ' +
      'One fictional young man in his twenties in a simple green vest smiles warmly while handing a folded paper leaflet with no printed text to a fictional adult visitor with a small travel bag. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/entrance-receptionist.png',
  },
  {
    id: 'water-cycle-technician',
    purpose: '水循環の技師（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph in a utility room of an orbital greenhouse, with a tall transparent water-recycling tank filled with clear water and aquatic plants. ' +
      'One fictional woman in her forties in practical grey overalls and safety glasses turns a large valve wheel with both hands while glancing at the water level in the tank. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/water-cycle-technician.png',
  },
  {
    id: 'dome-glass-cleaner',
    purpose: 'ドームのガラスの清掃員（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph inside a large curved glass dome of an orbital botanical garden, seen from a safe maintenance gantry. ' +
      'One fictional man in his thirties wearing a safety harness clipped to a rail and a light work suit wipes a glass panel with a long soft squeegee pole, with a distant Earth and stars beyond the glass. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/dome-glass-cleaner.png',
  },
  {
    id: 'seedling-courier',
    purpose: '苗の搬送員（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph in a bright white corridor of an orbital station lined with plants. ' +
      'One fictional young woman in her twenties with a ponytail and a green work vest pushes a wheeled cart stacked with trays of small seedlings, looking ahead along the corridor as she walks. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/seedling-courier.png',
  },
  {
    id: 'fungi-cultivator',
    purpose: '菌床の栽培員（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph in a cool, softly lit cultivation room of an orbital botanical garden, with tiered racks of mushroom beds. ' +
      'One fictional man in his fifties with a grey beard, a cap and a plain apron lifts a tray of pale mushrooms from a rack and inspects it closely. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/fungi-cultivator.png',
  },
  {
    id: 'pollinator-keeper',
    purpose: '受粉昆虫の飼育員（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph beside a transparent observation hive in an orbital greenhouse, with flowering plants all around. ' +
      'One fictional woman in her thirties wearing a light veiled hat and a pale work suit gently lifts a transparent hive panel and watches the bees on it, with a few bees drifting slowly in the air. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/pollinator-keeper.png',
  },
  {
    id: 'flower-workshop-instructor',
    purpose: '花の体験教室の講師（新規求人）',
    prompt:
      'A 16:9 documentary-style photograph of a bright workshop room in an orbital botanical garden with a long wooden table covered in fresh flowers and greenery. ' +
      'One fictional woman in her sixties with silver hair and a linen apron demonstrates arranging a small bouquet while three fictional adult participants follow along, each holding a stem. ' +
      WORK_TAIL,
    aspectRatio: '16:9',
    imageSize: '1K',
    outputFileName: 'recruits/flower-workshop-instructor.png',
  },
]
