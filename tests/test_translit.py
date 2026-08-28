"""اختبارات تحويل الأسماء العربية إلى لاتيني."""

from liftcore_translit import arabic_to_latin


def test_common_names_and_districts():
    assert arabic_to_latin('محمد') == 'Mohamed'
    assert arabic_to_latin('عبد العزيز') == 'Abdulaziz'
    assert arabic_to_latin('محمد عبد العزيز') == 'Mohamed Abdulaziz'
    assert arabic_to_latin('العزيزية') == 'Al-Azizia'
    assert arabic_to_latin('مكة') == 'Makkah'
