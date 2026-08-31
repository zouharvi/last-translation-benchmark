# <img src="web/src/assets/favicon.svg" height=30> Last Translation Benchmark

> **Abstract:**
> For scientific progress, we need benchmarks that test the limits of state-of-the-art models, and evaluation methods that inform us about failure cases.
> Standard benchmarks for machine translation evaluation are often either trivial (having few authentic mistakes) or unrealistic (overly synthetically contrived).
> Furthermore, automatic translation metrics become less reliable and reward-hacked as models get stronger, and their outputs are not actionable.
> Even gold human evaluation is not problem-free: it often lacks reproducibility, objectivity, and scalability.
> Overall, this prevents us from tracking objective progress in the field and from informing where we should focus next.
> We introduce the Last Translation Benchmark, which contains human-authored and peer-reviewed examples (texts, images, audio, videos) which break state-of-the-art machine translation models across many language pairs. 
> Each example has additionally handcrafted verification rules, which provide instructions on how to reliably and objectively evaluate any future translations of the example.
> The Last Translation Benchmark is a live dataset that accepts contributions.
> The latest version is `LTBv1`, containing accepted contributions prior to September 1st 2026, with future releases planned with subsequent contributions.

This repository contains the technical backend for the online platform as well as analysis scripts for the [Last Translation Benchmark paper](TODO TODO) and [data hosted at HuggingFace](TODO TODO) and [data hosted as a simple JSON](TODO TODO).
If you're interested in contributing, register at [last-translation-benchmark.vilda.net](https://last-translation-benchmark.vilda.net) (co-authorship offered after 10 approved submissions).
Alternatively you may also submit to the [model leaderboard](https://last-translation-benchmark.vilda.net/leaderboard-results).

<!-- <img width="1000" alt="Last Translation Benchmark poster" src="https://github.com/user-attachments/assets/f0971f5c-fc95-4d48-9f13-a01934b4913d" /> -->

## Data

The first version, `LTBv1` contains TODO hard-to-translate examples across many language pairs.
Each example contains the following:
- `source`: input text
- `source_lang`, `target_lang`: human-readable language names
- `source_lang_iso`, `target_lang_iso`: ISO639-3 language names, if they exist
- `source_instructions`: special translation instructions (optional)
- `source_media`: images, audio, and video are base64-encoded in a string (optional)
- `verification_rules`: a list rules that a translation needs to fulfill (one or more)
- `translations`: a list of translations by human and existing models also with information if they passed the verification rules
- `linguistics`: linguistic annotation of what causes the translation difficulty
- `tags`: which subsets this example belongs to (`LTBv1` is all, `LTBv1-text` is text-only, and `LTBv1-micro` is a micro text-only)

For example:
```json
{
  "id": 337, 
  "source_text": "Our new nurse used to play in the men's professional football team.", 
  "source_lang": "English", 
  "target_lang": "German", 
  "source_lang_iso": "eng", 
  "target_lang_iso": "deu", 
  "source_instructions": null, 
  "source_media": null, 
  "translations": [
    { "model": "human"           , "translation": "Unser neuer Krankenpfleger hat früher in der Profifußballmannschaft der Männer gespielt."        , "verified": [true]  }, 
    { "model": "Google Translate", "translation": "Unsere neue Krankenschwester spielte früher in der Profifußballmannschaft der Männer."           , "verified": [false] }, 
    { "model": "Lara"            , "translation": "Unsere neue Krankenschwester spielte früher in der Profi-Fußballmannschaft der Männer."          , "verified": [false] }, 
    { "model": "Gemini 3.1 Pro"  , "translation": "Unser neuer Krankenpfleger hat früher in der Profifußballmannschaft der Männer gespielt."        , "verified": [true]  }, 
    { "model": "Gemma 4"         , "translation": "Unsere neue Krankenschwester hat früher in der professionellen Männerfußballmannschaft gespielt.", "verified": [false] }, 
    ...
  ], 
  "verification_rules": ["Nurse must be translated to its male version (Krankenpfleger), not Krankenschwester."],  
  "linguistics": ["Target Gap: Morph to Words", "Morphological"],
  "tags": ["LTBv1", "LTBv1-text"]
}
```

## Citation & License

To cite this dataset, use the following. If the author list is too long, either truncate it or replace with `author={LTB}`.
```bibtex
@misc{last-translation-benchmark,
  title={Last Translation Benchmark},
  author={Vilém Zouhar and Niyati Bafna and Maike Züfle and Mukund Choudhary and Sara Rajaee and Pinzhen Chen and Jannis Vamvas and Sara Papi and Ona de Gibert and Patrícia Schmidtová and Leshem Choshen and Bhavitvya Malik and Orfeas Menis Mastromichalakis and Michelle Wastl and Jan Niehues and Rico Sennrich and Mrinmaya Sachan and Ondřej Bojar and Jörg Tiedemann and Alham Fikri Aji and Philipp Koehn and Kenton Murray and Christof Monz and Alexandra Birch and Sowmya Vajjala and Chalamalasetti Kranti and Cristina España-Bonet and David Kaczér and Shunta Asano and Daban Q. Jaff and Malik Marmonier and Nobin Sarwar and Vaisakhi Mishra and Hend Al-Khalifa and Nils Rehlinger and Juan Daniel Cuervo Villa and Saugata Purkayastha and Dominik Macháček and Jagannathan Ramanujam and Jonathan Tonglet and Heejin Do and Zuzana Nadova and Fred Philippy and Fabian Retkowski and Gabriele Sarti and Silvia Casola and Sangwon Ryu and Hanna Yukhymenko and Maria Lymperaiou and Avantica Vempati and Andrés Jerez and Shuaib Shuaib Yusuf and Maria Carmen Staiano and Sukannya Purkayastha and Ron Keinan and Adrian Cosma and Shubhashis Roy Dipta and Aviral Nigam and Vitalii Babenko and Erivan Inan and Wafa Aissa and Venkata Prasanth Kumar Gummadi and Mehdi Jafarzadeh and Lukas Edman and Kaiser Sun and Fatima Haouari and Valentin Scourneau and Shaomu Tan and Eliya Habba and Christian Hoang and Mohammad Sadegh Gholizadeh and Johannes-Rudolf David and Javier García Gilabert and Dipankar Srirag and Ruta Binkyte and Manar Ali and Ana-Maria Bucur and Sabry E. Farrag and Youssef Saber and Yihong Liu and Xiaochuang Yuan and Jean Maillard and Linh Vu and Sina Ahmadi and Philipp Mondorf and Kaustubh Dhole and Roman Wixinger and Manuel Tuor and Bo Chen and Shenbin Qian and Fida Mohammad Thoker and Sergey Troshin and Amir Arsalan Rezapour and Lance Calvin Lim Gamboa and Seth Aycock and Koel Dutta Chowdhury and Giuseppe Gallipoli and Cojocaru Nicoleta and Theresia Veronika Rampisela and Arafat Ahsan and Kätriin Kukk and Luan Thanh Nguyen and Hassan Soliman and Daryna Dementieva and Ngoc Quynh Tram Do and Manon Reusens and Jonathan Yahav and Mike Zhang and Kazuki Egashira and Marius Huber and Vladislav Poritski and R. Damanhuri and Luis Frentzen Salim and David Africa and Paul Gavrikov and Anumit Garg and Azmine Toushik Wasi and Andrianos Michail and Kamile Dementaviciute and L D M S Sai Teja and Dawei Zhu and Yi Fan and Wei Liu and Vatsal Venkatkrishna and Hongbin Na and Farzad Shami and Farhan Farsi and Elias Herranen and Sankalan Pal Chowdhury and Karen Sanchez and Ashok Urlana and Sekai Tully Carr and Reem Alzahrani and Priyaranjan Pattnayak and Emilian Radoi and Chenyi Zhao and Carlos Hinojosa and Andrea Gregor de Varda and Marii Ojastu and Gengyu Rao and Alex Flückiger and Rishit Dagli and Joy Olusanya and Jimson Paulo Layacan and Guy Kaplan and Ritwik Tiwari and Qiaoyuan Zheng and Pouya Sadeghi and Oksana Volchek and Isaac R Caswell and Bowen Yi and Blanka Kövér and Amir Hossein Yari and Zimu Wang and Zhengxiang Wang and Selja Keränen and Samuel Simko and Jan Kocoń and Enzo Doyen and Zaid Alyafeai and Vivek Harsha Lakkamaneni and Sophia Conrad and Panayiotis Panayiotou and Luis Lara and Jenny Chim and Jannatul Nayem and Deep Shah and Antonia Karamolegkou and Anmol Goel and Aishik Mandal and Tommaso Cerruti and Tomasz Limisiewicz and Raoyuan Zhao and Mykola Haltiuk and Amir Hossein Kargaran and Thura Aung and Naser Almousa and Beni Egressy and Rachel Bawden and Pawan Sasanka Ammanamanchi and Mateusz Lango and Terry Jingchen Zhang and Fidel Rodríguez Velásquez and Abdulaziz Nura Kani and Tosin Adewumi and Natchapon Jongwiriyanurak and Minh Ngoc Do and Marco Gaido and Lena Libon and Dzmitry Kuzmin and Beatrice Savoldi and Badal Nyalang and Antoine Taroni and Marek Šuppa and Deokhyung Kang and Andreas Simons and Stéphane J.P.S. Thunus and Rushikesh Zawar and Rayyan Merchant and Francesco Pinto and Ayush Sunil Munot and Ziyi Yang and Samuel Frontull and Muhammad Ravi Shulthan Habibi and Kenneth Enevoldsen and Harris Abdul Majid and Francesca Padovani and Tim Graf and Tatiana Bielakova and Sunisth Kumar and Sharifa Djurabaeva and Shaoxiong Ji and Sayuj Keerangatil and Raia Abu Ahmad and Pavel Stepachev and Jirui Qi and Aicha Chorana and Yuxing Lu and Yurii Paniv and Yolanda Xavier and Xiyan Fu and Shree Harsha Bokkahalli Satish and Shayan Bali and Papa Abdou Karim Karou Diallo and Matija Akrap and Marko Culjak and Kristýna Onderková and Joseph Attieh and Eran Yahav and Elisabeth Fittschen and Benoît Sagot and Bello Umar Bello and Jingwei Ni and Yu Fan},
  year={2026},
  url={https://last-translation-benchmark.vilda.net/},
  note={In preparation},
}
```

The source code in this repository is licensed under [MIT](LICENSE), and the data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.en).

## Development & Contributing

```bash
# requires python >=3.12, node >= 20
npm install --prefix web
npm run build --prefix web/
# use this one when developing
pip install -e ".[dev]" && pre-commit install -c .github/.pre-commit-config.yaml
# use this one when not developing
pip install -e .
# prints login URLs
python3 server
```

The `server/` contains source code for the server.
The `web/` is the frontend code (TypeScript) which, when built, goes to `server/static/` to be served by the server.

You can specify the `--host`, `--port` and `--host-public` arguments when starting the server. 
The last is used to show the login URLs.
For management of environment variables, create `config.toml` based on `config.template.toml`.
The instructions in [web/src/assets/instructions.html](web/src/assets/instructions.html) are based on upstream document written in Typst and should not be edited locally in this repo.

We welcome bugreports, hands-on, and research contributions.
AI-generated PRs are fine as long as you verify everything and take ownership of the changes.
This effort is organized by a collective of researchers from ETH Zurich, JHU, KIT, UvA, CUNI, and many others.
Reach out to [last-translation-benchmark@vilda.net](mailto:last-translation-benchmark@vilda.net) with inquiries.
Please do not reach out about the status of your pending submissions.
To speed up the review process, you can invite other speakers of your languages who can review your submissions or nominate yourself to be a reviewer.