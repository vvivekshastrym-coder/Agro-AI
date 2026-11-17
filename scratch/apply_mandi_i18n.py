with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update English dictionary
en_target = 'market_title: "Mandi Market",'
en_replacement = '''market_title: "Mandi Market",
    market_subtitle: "Master APMC Directory & Daily Price Intelligence",
    lbl_mandi_state: "STATE",
    lbl_mandi_district: "DISTRICT",
    lbl_mandi_commodity: "COMMODITY / CROP",
    search_market_placeholder: "🔍 Search APMC market e.g. Yeshwanthpur, Kolar, Byadgi...",
    load_more_markets: "Load More Markets ▾",
    market_official_badge: "Agmarknet Official",'''

assert en_target in content, "en_target not found"
content = content.replace(en_target, en_replacement, 1)

# 2. Update Kannada dictionary
kn_target = 'market_title: "ಮಂಡಿ ಮಾರುಕಟ್ಟೆ",'
kn_replacement = '''market_title: "ಮಂಡಿ ಮಾರುಕಟ್ಟೆ",
    market_subtitle: "ಅಧಿಕೃತ ಎಪಿಎಂಸಿ ಡೈರೆಕ್ಟರಿ ಮತ್ತು ದೈನಂದಿನ ಬೆಲೆಗಳು",
    lbl_mandi_state: "ರಾಜ್ಯ",
    lbl_mandi_district: "ಜಿಲ್ಲೆ",
    lbl_mandi_commodity: "ಬೆಳೆ / ಸರಕು",
    search_market_placeholder: "🔍 ಎಪಿಎಂಸಿ ಮಾರುಕಟ್ಟೆ ಹುಡುಕಿ (ಉದಾ: ಯಶವಂತಪುರ, ಕೋಲಾರ, ಬ್ಯಾಡಗಿ...)",
    load_more_markets: "ಇನ್ನಷ್ಟು ಮಾರುಕಟ್ಟೆಗಳನ್ನು ತೋರಿಸಿ ▾",
    market_official_badge: "ಅಧಿಕೃತ ಅಗ್ರ್ಮಾರ್ಕ್‌ನೆಟ್",'''

assert kn_target in content, "kn_target not found"
content = content.replace(kn_target, kn_replacement, 1)

# 3. Update Hindi dictionary
hi_target = '"market_title": "मंडी बाजार",'
hi_replacement = '''"market_title": "मंडी बाजार",
      "market_subtitle": "मास्टर एपीएमसी डायरेक्टरी एवं दैनिक भाव",
      "lbl_mandi_state": "राज्य",
      "lbl_mandi_district": "जिला",
      "lbl_mandi_commodity": "फसल / जींस",
      "search_market_placeholder": "🔍 एपीएमसी मंडी खोजें (उदा: यशवंतपुर, कोलार, ब्याडगी...)",
      "load_more_markets": "और अधिक मंडियां देखें ▾",
      "market_official_badge": "आधिकारिक एग्मार्कनेट",'''

assert hi_target in content, "hi_target not found"
content = content.replace(hi_target, hi_replacement, 1)

# 4. Update applyTranslations function
apply_target = '''  // Mandi Market Screen
  setTxt('marketTitle', dict.market_title);
  setTxt('marketForecastBtn', dict.market_forecast_btn);'''

apply_replacement = '''  // Mandi Market Screen
  setTxt('marketTitle', dict.market_title);
  setTxt('marketSubtitle', dict.market_subtitle || 'Master APMC Directory & Daily Price Intelligence');
  setTxt('lblMandiState', dict.lbl_mandi_state || 'STATE');
  setTxt('lblMandiDistrict', dict.lbl_mandi_district || 'DISTRICT');
  setTxt('lblMandiCrop', dict.lbl_mandi_commodity || 'COMMODITY / CROP');
  setTxt('mandiLoadMoreBtn', dict.load_more_markets || 'Load More Markets ▾');
  setTxt('marketSourceBadge', dict.market_official_badge || 'Agmarknet Official');
  const marketSearchInput = document.getElementById('marketSearchInput');
  if (marketSearchInput && dict.search_market_placeholder) {
    marketSearchInput.placeholder = dict.search_market_placeholder;
  }
  setTxt('marketForecastBtn', dict.market_forecast_btn);'''

assert apply_target in content, "apply_target not found"
content = content.replace(apply_target, apply_replacement, 1)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully updated index.html with Mandi translations and applyTranslations bindings.")
