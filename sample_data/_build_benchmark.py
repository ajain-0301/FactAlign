"""Generates sample_data/benchmark.json. Re-run: python sample_data/_build_benchmark.py"""
import json, pathlib

NOTE = ("SYNTHETIC demo text written by the project author. Places, people, organisations and figures are invented. "
        "Reference summaries and claim labels were written by the author, are NOT a peer-reviewed annotated corpus, "
        "and the set is far too small for research conclusions.")

def doc(id, topic, lang, title, source, ref, claims):
    return {"id": id, "pair_id": topic, "language": lang, "title": title, "source": source,
            "reference_summary": ref,
            "labeled_claims": [{"claim": c, "label": l} for c, l in claims]}

D = []
# ---------------------------------------------------------------- A: air quality
D.append(doc("air-en", "air", "en", "Haritpur air quality plan (English)",
 "Haritpur Municipal Corporation announced a new air quality plan on 12 March 2024. The average Air Quality Index in the city was 182 in 2023, which is 14% higher than in 2022. Commissioner Meera Rao said the plan will cost 250 crore rupees and will be completed by December 2026. The corporation will install 40 monitoring stations and replace 500 diesel buses with electric buses. Construction dust and vehicle emissions are the two biggest sources of pollution, according to a study by the Haritpur Institute of Technology. The plan does not include a ban on private cars.",
 "Haritpur Municipal Corporation announced on 12 March 2024 a 250 crore rupee air quality plan, to finish by December 2026, with 40 monitoring stations and 500 electric buses replacing diesel ones. The city's average AQI was 182 in 2023, 14% higher than in 2022, and the plan does not ban private cars.",
 [("The plan will cost 250 crore rupees.", "supported"), ("The plan will be completed by December 2025.", "contradicted"),
  ("The plan includes a ban on private cars.", "contradicted"), ("The plan was approved by the state government.", "unverifiable")]))
D.append(doc("air-hi", "air", "hi", "हरितपुर वायु गुणवत्ता योजना (हिंदी)",
 "हरितपुर नगर निगम ने 12 मार्च 2024 को वायु गुणवत्ता की नई योजना की घोषणा की। शहर का औसत वायु गुणवत्ता सूचकांक 2023 में 182 रहा, जो 2022 की तुलना में 14 प्रतिशत अधिक है। आयुक्त मीरा राव ने कहा कि योजना पर 250 करोड़ रुपये खर्च होंगे और यह दिसंबर 2026 तक पूरी होगी। निगम 40 निगरानी केंद्र लगाएगा और 500 डीज़ल बसों की जगह इलेक्ट्रिक बसें चलाएगा। हरितपुर प्रौद्योगिकी संस्थान के एक अध्ययन के अनुसार निर्माण की धूल और वाहनों का उत्सर्जन प्रदूषण के दो सबसे बड़े स्रोत हैं। योजना में निजी कारों पर प्रतिबंध शामिल नहीं है।",
 "हरितपुर नगर निगम ने 12 मार्च 2024 को 250 करोड़ रुपये की वायु गुणवत्ता योजना की घोषणा की, जो दिसंबर 2026 तक पूरी होगी और जिसमें 40 निगरानी केंद्र तथा 500 डीज़ल बसों की जगह इलेक्ट्रिक बसें शामिल हैं। 2023 में शहर का औसत सूचकांक 182 था, जो 2022 से 14 प्रतिशत अधिक है, और योजना में निजी कारों पर प्रतिबंध नहीं है।",
 [("योजना पर 250 करोड़ रुपये खर्च होंगे।", "supported"), ("योजना दिसंबर 2025 तक पूरी होगी।", "contradicted"),
  ("योजना में निजी कारों पर प्रतिबंध शामिल है।", "contradicted"), ("योजना को राज्य सरकार ने मंज़ूरी दे दी है।", "unverifiable")]))
D.append(doc("air-hinglish", "air", "hinglish", "Haritpur air quality plan (Hinglish)",
 "Haritpur Municipal Corporation ने 12 March 2024 को नया air quality plan announce किया। शहर का average Air Quality Index 2023 में 182 रहा, जो 2022 के मुकाबले 14% ज़्यादा है। Commissioner Meera Rao ने बताया कि इस plan पर 250 crore rupees खर्च होंगे और यह December 2026 तक complete होगा। Corporation 40 monitoring stations लगाएगा और 500 diesel buses की जगह electric buses चलाएगा। Haritpur Institute of Technology की एक study के मुताबिक construction dust और vehicle emissions pollution के दो सबसे बड़े sources हैं। Plan में private cars पर ban शामिल नहीं है।",
 "Haritpur Municipal Corporation ने 12 March 2024 को 250 crore rupees का air quality plan announce किया, जो December 2026 तक complete होगा और जिसमें 40 monitoring stations व 500 electric buses शामिल हैं। 2023 में शहर का average AQI 182 था, जो 2022 से 14% ज़्यादा है, और plan में private cars पर ban नहीं है।",
 [("Plan पर 250 crore rupees खर्च होंगे।", "supported"), ("Plan December 2025 तक complete होगा।", "contradicted"),
  ("Plan में private cars पर ban शामिल है।", "contradicted"), ("Plan को state government ने approve कर दिया है।", "unverifiable")]))
# ---------------------------------------------------------------- B: digital payments
D.append(doc("pay-en", "pay", "en", "SwiftPay quarterly report (English)",
 "SwiftPay, a digital payments platform, processed 9.4 billion transactions in the first quarter of 2024. The company said the number rose 31% from the same period last year. Chief executive Arjun Mehta announced on 5 April 2024 that SwiftPay will launch offline payments in 120 districts by September 2024. The company also stated that it has not charged any fee to customers for payments below 2,000 rupees. Rural users made up 38% of new users, according to the quarterly report. Regulators have not yet reviewed the offline payments feature.",
 "SwiftPay processed 9.4 billion transactions in Q1 2024, up 31% year on year. On 5 April 2024 CEO Arjun Mehta announced offline payments in 120 districts by September 2024; rural users were 38% of new users and regulators have not yet reviewed the feature.",
 [("SwiftPay processed 9.4 billion transactions in the first quarter of 2024.", "supported"),
  ("SwiftPay processed 4.9 billion transactions in the first quarter of 2024.", "contradicted"),
  ("Regulators have reviewed the offline payments feature.", "contradicted"),
  ("SwiftPay plans to launch in international markets.", "unverifiable")]))
D.append(doc("pay-hi", "pay", "hi", "स्विफ्टपे तिमाही रिपोर्ट (हिंदी)",
 "डिजिटल भुगतान मंच स्विफ्टपे ने 2024 की पहली तिमाही में 9.4 अरब लेन-देन संसाधित किए। कंपनी ने बताया कि यह संख्या पिछले साल की इसी अवधि से 31 प्रतिशत अधिक है। मुख्य कार्यकारी अर्जुन मेहता ने 5 अप्रैल 2024 को घोषणा की कि स्विफ्टपे सितंबर 2024 तक 120 ज़िलों में ऑफ़लाइन भुगतान की सुविधा शुरू करेगा। कंपनी ने यह भी कहा कि 2,000 रुपये से कम के भुगतान पर ग्राहकों से कोई शुल्क नहीं लिया गया है। तिमाही रिपोर्ट के अनुसार नए उपयोगकर्ताओं में ग्रामीण उपयोगकर्ता 38 प्रतिशत थे। नियामकों ने अभी तक ऑफ़लाइन भुगतान सुविधा की समीक्षा नहीं की है।",
 "स्विफ्टपे ने 2024 की पहली तिमाही में 9.4 अरब लेन-देन संसाधित किए, जो पिछले साल से 31 प्रतिशत अधिक है। अर्जुन मेहता ने 5 अप्रैल 2024 को सितंबर 2024 तक 120 ज़िलों में ऑफ़लाइन भुगतान शुरू करने की घोषणा की; नए उपयोगकर्ताओं में 38 प्रतिशत ग्रामीण थे और नियामकों ने सुविधा की समीक्षा नहीं की है।",
 [("स्विफ्टपे ने 2024 की पहली तिमाही में 9.4 अरब लेन-देन संसाधित किए।", "supported"),
  ("स्विफ्टपे सितंबर 2025 तक 120 ज़िलों में ऑफ़लाइन भुगतान शुरू करेगा।", "contradicted"),
  ("नियामकों ने ऑफ़लाइन भुगतान सुविधा की समीक्षा की है।", "contradicted"),
  ("स्विफ्टपे ने विदेशी बाज़ारों में विस्तार की योजना बनाई है।", "unverifiable")]))
D.append(doc("pay-hinglish", "pay", "hinglish", "SwiftPay quarterly report (Hinglish)",
 "Digital payments platform SwiftPay ने 2024 की पहली तिमाही में 9.4 billion transactions process किए। Company के मुताबिक यह number पिछले साल की same period से 31% ज़्यादा है। Chief executive Arjun Mehta ने 5 April 2024 को announce किया कि SwiftPay September 2024 तक 120 districts में offline payments launch करेगा। Company ने यह भी कहा कि 2,000 rupees से कम के payments पर customers से कोई fee नहीं ली गई है। Quarterly report के अनुसार new users में rural users 38% थे। Regulators ने अभी तक offline payments feature को review नहीं किया है।",
 "SwiftPay ने 2024 की पहली तिमाही में 9.4 billion transactions process किए, जो पिछले साल से 31% ज़्यादा है। Arjun Mehta ने 5 April 2024 को September 2024 तक 120 districts में offline payments launch करने की बात कही; new users में 38% rural थे और regulators ने feature को review नहीं किया है।",
 [("SwiftPay ने 2024 की पहली तिमाही में 9.4 billion transactions process किए।", "supported"),
  ("Rural users new users में 58% थे।", "contradicted"),
  ("Regulators ने offline payments feature को review कर लिया है।", "contradicted"),
  ("SwiftPay ने international markets में launch करने की योजना बनाई है।", "unverifiable")]))
# ---------------------------------------------------------------- C: heavy rain
D.append(doc("rain-en", "rain", "en", "Kisanpur heavy rain relief (English)",
 "Heavy rain hit Kisanpur district from 18 July to 21 July 2024, damaging crops on 22,000 hectares. District Collector Ramesh Iyer said that 15,000 farmers will receive relief payments of 8,000 rupees each by 10 August 2024. The meteorological department recorded 310 millimetres of rain in four days, which is 60% of the district's average monsoon rainfall. Two relief camps have been opened in Kisanpur town. Officials said that no deaths have been reported so far. The state government has not yet announced a crop insurance payout.",
 "Heavy rain hit Kisanpur district from 18 to 21 July 2024, damaging crops on 22,000 hectares. 15,000 farmers will receive 8,000 rupees each by 10 August 2024; no deaths have been reported and no crop insurance payout has been announced.",
 [("15,000 farmers will receive relief payments of 8,000 rupees each.", "supported"),
  ("Crops were damaged on 12,000 hectares.", "contradicted"),
  ("The state government has announced a crop insurance payout.", "contradicted"),
  ("The rain was caused by a cyclone.", "unverifiable")]))
D.append(doc("rain-hi", "rain", "hi", "किसानपुर भारी बारिश राहत (हिंदी)",
 "किसानपुर ज़िले में 18 जुलाई से 21 जुलाई 2024 के बीच भारी बारिश हुई, जिससे 22,000 हेक्टेयर में फ़सलें नष्ट हो गईं। ज़िलाधिकारी रमेश अय्यर ने कहा कि 15,000 किसानों को 10 अगस्त 2024 तक 8,000 रुपये प्रति किसान की राहत राशि दी जाएगी। मौसम विभाग ने चार दिनों में 310 मिलीमीटर बारिश दर्ज की, जो ज़िले की औसत मानसूनी वर्षा का 60 प्रतिशत है। किसानपुर शहर में दो राहत शिविर खोले गए हैं। अधिकारियों ने बताया कि अब तक किसी की मृत्यु की सूचना नहीं है। राज्य सरकार ने अभी तक फ़सल बीमा भुगतान की घोषणा नहीं की है।",
 "किसानपुर ज़िले में 18 से 21 जुलाई 2024 के बीच भारी बारिश से 22,000 हेक्टेयर फ़सलें नष्ट हुईं। 15,000 किसानों को 10 अगस्त 2024 तक 8,000 रुपये प्रति किसान मिलेंगे; किसी की मृत्यु की सूचना नहीं है और फ़सल बीमा भुगतान की घोषणा नहीं हुई है।",
 [("15,000 किसानों को 8,000 रुपये प्रति किसान की राहत राशि दी जाएगी।", "supported"),
  ("फ़सलें 12,000 हेक्टेयर में नष्ट हुईं।", "contradicted"),
  ("राज्य सरकार ने फ़सल बीमा भुगतान की घोषणा की है।", "contradicted"),
  ("बारिश चक्रवात के कारण हुई।", "unverifiable")]))
D.append(doc("rain-hinglish", "rain", "hinglish", "Kisanpur heavy rain relief (Hinglish)",
 "Kisanpur district में 18 July से 21 July 2024 के बीच heavy rain हुई, जिससे 22,000 hectares में crops damage हो गईं। District Collector Ramesh Iyer ने कहा कि 15,000 farmers को 10 August 2024 तक 8,000 rupees per farmer relief payment दिया जाएगा। Meteorological department ने चार दिनों में 310 millimetres rain record की, जो district की average monsoon rainfall का 60% है। Kisanpur town में दो relief camps खोले गए हैं। Officials ने बताया कि अब तक किसी की death की report नहीं है। State government ने अभी तक crop insurance payout announce नहीं किया है।",
 "Kisanpur district में 18 से 21 July 2024 के बीच heavy rain से 22,000 hectares में crops damage हुईं। 15,000 farmers को 10 August 2024 तक 8,000 rupees per farmer मिलेंगे; किसी की death की report नहीं है और crop insurance payout announce नहीं हुआ है।",
 [("15,000 farmers को 8,000 rupees per farmer relief payment दिया जाएगा।", "supported"),
  ("Relief payment 10 September 2024 तक दिया जाएगा।", "contradicted"),
  ("State government ने crop insurance payout announce कर दिया है।", "contradicted"),
  ("बारिश cyclone की वजह से हुई।", "unverifiable")]))

out = {
 "dataset": "FactAlign-synthetic-demo-v1", "note": NOTE, "items": D,
 "assignment_examples": [
   {"id": "ex-codemixed", "language": "hinglish", "title": "Assignment example: code-mixed sentence",
    "text": "Climate change ki wajah se temperature continuously increase ho raha hai, which is a serious concern for everyone."},
   {"id": "ex-indic", "language": "hi", "title": "Assignment example: Indic sentence", "text": "भारत में प्रदूषण का स्तर लगातार बढ़ रहा है।"},
   {"id": "ex-indic-cm", "language": "hinglish", "title": "Assignment example: Indic sentence, code-mixed", "text": "भारत में pollution का level लगातार increase हो रहा है।"},
 ],
}
pathlib.Path(__file__).with_name("benchmark.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(len(D), "documents,", sum(len(d["labeled_claims"]) for d in D), "labelled claims")
