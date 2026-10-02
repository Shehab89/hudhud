export type Block = { id: string; title: string; body: string[] };

export const en: Block[] = [
  { id: "principles", title: "Five measures, kept apart", body: [
    "The platform never combines its measures into a single \"bias\" score. Each answers a different question and is stored, shown and exported separately.",
    "A. Source orientation: who the outlet is (ownership, funding, stated editorial alignment), documented with evidence, a confidence and a method, and dated because outlets change. It is not a reliability rating.",
    "B. Article sentiment: the overall tone of the text (positive, neutral, negative, or uncertain when the evidence is weak), plus emotions and tone such as accusatory or conciliatory.",
    "C. Framing: how the text presents an issue (for example humanitarian, security, sovereignty or legitimacy), always with the sentence that shows it.",
    "D. Topic: what the article is about, from a curated taxonomy and from data-driven topic models.",
    "E. Actor-targeted sentiment: how a specific sentence that names an actor reads, with that sentence kept as evidence. It describes wording, not the actor's conduct.",
  ] },
  { id: "sources", title: "Source registry", body: [
    "Only real, verified outlets are registered. Feed URLs are checked before they are added; outlets without a usable feed are kept as inactive records rather than given invented URLs.",
    "Each outlet records where its newsroom operates (Sana'a-controlled areas, government-controlled areas, STC-controlled areas, outside Yemen, or unknown). This is a fact about location used for split views, not an orientation.",
    "Orientation labels require evidence links. Where evidence is thin the label is \"unknown\" with low confidence. Orientation rows have validity dates, so a change of ownership does not rewrite history.",
  ] },
  { id: "collection", title: "Collection", body: [
    "Articles come from publishers' RSS/Atom feeds and from Google News and GDELT queries about Yemen; aggregator items are attributed to the original publisher when its domain is registered.",
    "The collector respects robots.txt, identifies itself, uses conditional requests, and never bypasses paywalls, logins, CAPTCHAs or other access controls. It stores metadata and the feed's short excerpt, not full texts; readers are linked to the publisher.",
    "General-interest feeds are filtered for Yemen relevance using a multilingual term list. Collection runs daily; failures are retried with backoff and logged per feed, and one failing source never stops the run.",
  ] },
  { id: "language", title: "Language and Arabic text", body: [
    "Language is detected per article (12 languages) with a confidence; mixed-script texts are flagged. Original texts are never replaced by translations.",
    "Arabic matching normalises alef and hamza forms, ta marbuta, alef maqsura, diacritics and tatweel, and accepts attached prefixes (و ف ب ل ك ال) so that, for example, غارة also matches الغارات.",
  ] },
  { id: "dedup", title: "Duplicates, syndication and stories", body: [
    "Duplicates are detected in layers: canonical URL, identical content, near-identical headlines (MinHash plus fuzzy matching) and embedding similarity.",
    "Copies of the same text by different outlets are marked as syndicated and linked to the earliest copy. Articles about the same story are grouped into story clusters, which count both the outlets that covered a story and the independent ones that did not merely republish wire copy.",
  ] },
  { id: "classification", title: "Classification and confidence routing", body: [
    "Every automated label has a confidence. Results above 0.85 are accepted; between 0.60 and 0.85 a second model (multilingual zero-shot NLI) re-scores them; below 0.60 the item is sent to the language model when one is configured, and otherwise stays labelled uncertain.",
    "Every result records the method, the model and its version, the prompt version for language-model results, and the analysis version, so any number can be traced and re-computed.",
  ] },
  { id: "affect", title: "Sentiment, emotion and tone", body: [
    "Sentiment uses multilingual transformer models (XLM-RoBERTa, with an Arabic-specific CAMeLBERT model for Arabic). When models are unavailable a transparent lexicon is used and the result is labelled as such.",
    "News is mostly neutral reporting of negative events. A negative label therefore usually reflects the events described, not the outlet's attitude.",
  ] },
  { id: "framing", title: "Framing", body: [
    "Eighteen frames are defined with cue terms in several languages. A frame is recorded only with the sentence that triggered it, quoted from the article, and can be confirmed by a zero-shot model.",
    "Language-model frame suggestions are kept only when their evidence quote appears verbatim in the article.",
  ] },
  { id: "actors", title: "Actors and terminology", body: [
    "A curated knowledge base lists political actors, armed groups, states, international organisations and public figures, with their names in many languages. Names are not neutral: each alias is tagged as official, self-designation, common, descriptive or critical, with notes on who typically uses it. Only public actors are profiled.",
    "Actor-targeted sentiment is computed only for sentences that name an actor and are clearly polar, and the sentence is shown with the score.",
  ] },
  { id: "topics", title: "Topics and trends", body: [
    "Data-driven topics are found by clustering multilingual sentence embeddings (BERTopic with UMAP and HDBSCAN on large corpora; k-means otherwise) and described with class-based TF-IDF terms. Coherence (NPMI) and diversity are reported for every model. Language-model labels, when enabled, are stored next to the statistical terms, never instead of them.",
    "New articles are assigned to existing topics daily; models are refitted weekly and linked to persistent topics by centroid similarity, which keeps continuity across refits and across languages.",
    "A theme is emerging when its articles at least double week on week, with at least five articles from three outlets; declining when they halve from at least five. Volume alone never makes a topic \"important\".",
  ] },
  { id: "events", title: "Events", body: [
    "An event is recorded when a trigger term (for example airstrike, clashes, cholera) and a known place occur in the same sentence. Reports of the same type, place and day are merged. These are reports in coverage, not verified incident data; for casualty data use dedicated datasets such as ACLED.",
  ] },
  { id: "humans", title: "Human review and drift", body: [
    "Registered researchers can submit corrections to any label. Accepted corrections to sentiment, category and frame become the current result, marked as human with the model's earlier output kept for comparison; all corrections are kept for evaluation and retraining.",
    "Drift checks compare the last seven days with the previous seven (languages, source groups, sentiment, vocabulary) and flag shifts that may signal a broken feed or a model problem rather than a real change in coverage.",
  ] },
  { id: "limits", title: "Known limitations", body: [
    "Coverage reflects which outlets publish usable feeds; Yemeni outlets with no feed, social media, radio and television are under-represented.",
    "Automated labels have error rates, and accuracy is lower for dialectal Arabic, short headlines and less-resourced languages. Treat small differences as noise.",
    "Synthetic DEMO DATA is used for development and demonstrations. It is flagged on every record, in exports and with a banner.",
  ] },
];

export const ar: Block[] = [
  { id: "principles", title: "خمسة مقاييس منفصلة", body: [
    "لا تدمج المنصة مقاييسها أبداً في درجة واحدة لـ«الانحياز». كل مقياس يجيب عن سؤال مختلف، ويُحفظ ويُعرض ويُصدَّر منفصلاً.",
    "أ. توجّه المصدر: من هو المنفذ (الملكية والتمويل والانحياز التحريري المعلن)، موثّقاً بالأدلة ودرجة ثقة وطريقة، ومؤرَّخاً لأن المنافذ تتغير. وليس تقييماً للمصداقية.",
    "ب. مشاعر المقال: النبرة العامة للنص (إيجابية أو محايدة أو سلبية، أو غير مؤكدة عند ضعف الدليل)، إضافة إلى العواطف والنبرة كالاتهامية أو التصالحية.",
    "ج. التأطير: كيف يقدّم النص القضية (إنسانياً أو أمنياً أو من زاوية السيادة أو الشرعية مثلاً)، دائماً مع الجملة التي تُظهر ذلك.",
    "د. الموضوع: عمّ يتحدث المقال، من تصنيف مُعدّ مسبقاً ومن نماذج مواضيع مستخلصة من البيانات.",
    "هـ. المشاعر تجاه الفاعلين: كيف تُصاغ جملة بعينها تذكر فاعلاً ما، مع الاحتفاظ بالجملة دليلاً. تصف الصياغة لا سلوك الفاعل.",
  ] },
  { id: "sources", title: "سجل المصادر", body: [
    "لا تُسجَّل إلا منافذ حقيقية متحقَّق منها. تُفحص روابط الخلاصات قبل إضافتها، والمنافذ التي لا تملك خلاصة صالحة تبقى سجلات غير نشطة بدلاً من اختلاق روابط لها.",
    "يسجّل كل منفذ مكان عمل غرفة أخباره (مناطق سيطرة صنعاء، مناطق سيطرة الحكومة، مناطق سيطرة الانتقالي، خارج اليمن، أو غير معروف). هذه معلومة عن الموقع تُستخدم في العروض المقارنة، وليست توجّهاً.",
    "تتطلب أوصاف التوجّه روابط أدلة. وحين تكون الأدلة ضعيفة يكون الوصف «غير معروف» بثقة منخفضة. ولسجلات التوجّه تواريخ صلاحية، فلا يعيد تغيير الملكية كتابة التاريخ.",
  ] },
  { id: "collection", title: "الجمع", body: [
    "تأتي المقالات من خلاصات RSS/Atom للناشرين ومن استعلامات Google News وGDELT عن اليمن، وتُنسب مواد المجمّعات إلى الناشر الأصلي متى كان نطاقه مسجّلاً.",
    "يحترم الجامع ملف robots.txt ويعرّف بنفسه ويستخدم الطلبات المشروطة، ولا يتجاوز أبداً جدران الدفع أو تسجيل الدخول أو CAPTCHA أو أي ضوابط وصول. ويحفظ البيانات الوصفية والمقتطف القصير من الخلاصة، لا النصوص الكاملة، ويُحال القارئ إلى الناشر.",
    "تُصفّى الخلاصات العامة بحسب صلتها باليمن عبر قائمة مصطلحات متعددة اللغات. يعمل الجمع يومياً، وتُعاد المحاولة عند الفشل مع تأخير متزايد ويُسجَّل لكل خلاصة، ولا يوقف تعطّل مصدر واحد التشغيل.",
  ] },
  { id: "language", title: "اللغة والنص العربي", body: [
    "تُكتشف لغة كل مقال (12 لغة) مع درجة ثقة، وتُوسم النصوص مختلطة الكتابة. لا يُستبدل النص الأصلي بترجمة أبداً.",
    "توحّد المطابقة العربية أشكال الألف والهمزة والتاء المربوطة والألف المقصورة وتزيل التشكيل والتطويل، وتقبل السوابق المتصلة (و ف ب ل ك ال)، فتطابق «غارة» مثلاً «الغارات».",
  ] },
  { id: "dedup", title: "التكرار والنقل والقصص", body: [
    "يُكشف التكرار على طبقات: الرابط الموحّد، والمحتوى المتطابق، والعناوين شبه المتطابقة (MinHash مع مطابقة تقريبية)، وتشابه التمثيلات الدلالية.",
    "تُوسم نسخ النص نفسه لدى منافذ مختلفة بأنها منقولة وتُربط بأقدم نسخة. وتُجمع المقالات عن القصة نفسها في مجموعات قصص تحسب المنافذ التي غطّت القصة والمستقلة منها التي لم تكتفِ بإعادة نشر برقية وكالة.",
  ] },
  { id: "classification", title: "التصنيف وتوجيه الثقة", body: [
    "لكل تصنيف آلي درجة ثقة. تُقبل النتائج فوق 0.85، وبين 0.60 و0.85 يعيد نموذج ثانٍ (استدلال لغوي متعدد اللغات دون تدريب مسبق) تقييمها، وتحت 0.60 يُرسل العنصر إلى النموذج اللغوي إن كان مُعدّاً، وإلا يبقى موسوماً بغير مؤكد.",
    "تسجّل كل نتيجة الطريقة والنموذج وإصداره وإصدار التعليمات لنتائج النموذج اللغوي وإصدار التحليل، فيمكن تتبّع أي رقم وإعادة حسابه.",
  ] },
  { id: "affect", title: "المشاعر والعواطف والنبرة", body: [
    "تستخدم المشاعر نماذج محوّلات متعددة اللغات (XLM-RoBERTa، ونموذج CAMeLBERT المخصص للعربية). وعند تعذّر النماذج يُستخدم معجم شفاف وتُوسم النتيجة بذلك.",
    "الأخبار في معظمها تغطية محايدة لأحداث سلبية؛ لذا يعكس الوسم السلبي عادة الأحداث الموصوفة لا موقف المنفذ.",
  ] },
  { id: "framing", title: "التأطير", body: [
    "عُرّف ثمانية عشر إطاراً بمصطلحات دالة بعدة لغات. لا يُسجَّل إطار إلا مع الجملة التي استدعته مقتبسة من المقال، ويمكن تأكيده بنموذج دون تدريب مسبق.",
    "لا تُقبل اقتراحات الأطر من النموذج اللغوي إلا إذا ورد اقتباس الدليل حرفياً في المقال.",
  ] },
  { id: "actors", title: "الفاعلون والمصطلحات", body: [
    "تضم قاعدة معرفة مُعدّة الفاعلين السياسيين والجماعات المسلحة والدول والمنظمات الدولية والشخصيات العامة، بأسمائهم بلغات عديدة. الأسماء ليست محايدة: كل اسم موسوم بأنه رسمي أو تسمية ذاتية أو شائع أو وصفي أو نقدي، مع ملاحظات عمّن يستخدمه عادة. ولا تُنشأ ملفات إلا للفاعلين العامّين.",
    "لا تُحسب المشاعر تجاه فاعل إلا للجمل التي تذكره وتحمل قطبية واضحة، وتُعرض الجملة مع الدرجة.",
  ] },
  { id: "topics", title: "المواضيع والاتجاهات", body: [
    "تُكتشف المواضيع بتجميع تمثيلات الجمل متعددة اللغات (BERTopic مع UMAP وHDBSCAN للمدوّنات الكبيرة، وk-means في غيرها) وتُوصف بمصطلحات TF-IDF على مستوى الفئة. ويُعلن الاتساق (NPMI) والتنوع لكل نموذج. وتُحفظ تسميات النموذج اللغوي، إن فُعّل، بجانب المصطلحات الإحصائية لا بدلاً منها.",
    "تُسند المقالات الجديدة يومياً إلى المواضيع القائمة، ويُعاد تدريب النماذج أسبوعياً وتُربط بمواضيع دائمة عبر تشابه المراكز، مما يحفظ الاستمرارية عبر الإصدارات واللغات.",
    "يكون الموضوع صاعداً إذا تضاعفت مقالاته على الأقل أسبوعياً، مع خمس مقالات على الأقل من ثلاثة منافذ؛ ومتراجعاً إذا انخفضت إلى النصف من خمس مقالات على الأقل. الحجم وحده لا يجعل موضوعاً «مهماً».",
  ] },
  { id: "events", title: "الأحداث", body: [
    "يُسجَّل حدث عند ورود مصطلح دال (كغارة أو اشتباكات أو كوليرا) ومكان معروف في الجملة نفسها، وتُدمج البلاغات من النوع والمكان واليوم نفسه. هذه بلاغات في التغطية وليست بيانات حوادث متحقَّقاً منها؛ ولبيانات الضحايا تُستخدم مجموعات مخصصة مثل ACLED.",
  ] },
  { id: "humans", title: "المراجعة البشرية ورصد الانحراف", body: [
    "يمكن للباحثين المسجّلين تقديم تصحيحات لأي تصنيف. تصبح التصحيحات المقبولة للمشاعر والفئة والإطار هي النتيجة المعتمدة، مع وسمها بأنها بشرية والاحتفاظ بمخرجات النموذج السابقة للمقارنة، وتُحفظ جميع التصحيحات لأغراض التقييم وإعادة التدريب.",
    "تقارن فحوص الانحراف الأيام السبعة الأخيرة بالسبعة السابقة (اللغات ومجموعات المصادر والمشاعر والمفردات) وتنبّه إلى تحوّلات قد تدل على خلاصة معطّلة أو مشكلة في نموذج لا على تغيّر حقيقي في التغطية.",
  ] },
  { id: "limits", title: "حدود معروفة", body: [
    "تعكس التغطية المنافذ التي تنشر خلاصات صالحة؛ والمنافذ اليمنية بلا خلاصات ووسائل التواصل والإذاعة والتلفزيون ممثلة تمثيلاً ناقصاً.",
    "للتصنيفات الآلية معدلات خطأ، وتقل الدقة في العربية اللهجية والعناوين القصيرة واللغات الأقل موارد. تعامل مع الفروق الصغيرة على أنها ضجيج.",
    "تُستخدم البيانات التجريبية المُصطنعة (DEMO DATA) للتطوير والعرض، وهي موسومة في كل سجل وفي التصدير وبشريط تنبيه.",
  ] },
];
