-- Seed real GPS coordinates for all Oman governorates and wilayats
-- Coordinates are approximate center-points of each area

-- ============================================
-- GOVERNORATES (States) — by name_en match
-- ============================================
UPDATE locations SET latitude = 23.5880, longitude = 58.3829 WHERE name_en = 'Muscat Governorate' AND type = 'state';
UPDATE locations SET latitude = 17.0151, longitude = 54.0924 WHERE name_en = 'Dhofar Governorate' AND type = 'state';
UPDATE locations SET latitude = 22.9333, longitude = 57.5333 WHERE name_en = 'Al Dakhiliyah Governorate' AND type = 'state';
UPDATE locations SET latitude = 24.3500, longitude = 56.7000 WHERE name_en = 'North Al Batinah Governorate' AND type = 'state';
UPDATE locations SET latitude = 23.6000, longitude = 57.5000 WHERE name_en = 'South Al Batinah Governorate' AND type = 'state';
UPDATE locations SET latitude = 22.5000, longitude = 58.5000 WHERE name_en = 'North Al Sharqiyah Governorate' AND type = 'state';
UPDATE locations SET latitude = 22.5667, longitude = 59.5289 WHERE name_en = 'South Al Sharqiyah Governorate' AND type = 'state';
UPDATE locations SET latitude = 23.3000, longitude = 56.5000 WHERE name_en = 'Al Dhahirah Governorate' AND type = 'state';
UPDATE locations SET latitude = 24.2500, longitude = 55.8333 WHERE name_en = 'Al Buraimi Governorate' AND type = 'state';
UPDATE locations SET latitude = 20.5000, longitude = 56.5000 WHERE name_en = 'Al Wusta Governorate' AND type = 'state';
UPDATE locations SET latitude = 26.1700, longitude = 56.2500 WHERE name_en = 'Musandam Governorate' AND type = 'state';

-- ============================================
-- WILAYATS (Cities) — by name_en match
-- ============================================

-- Muscat Governorate
UPDATE locations SET latitude = 23.5880, longitude = 58.3829 WHERE name_en = 'Muscat' AND type = 'city';
UPDATE locations SET latitude = 23.6167, longitude = 58.5667 WHERE name_en = 'Muttrah' AND type = 'city';
UPDATE locations SET latitude = 23.5619, longitude = 58.3969 WHERE name_en = 'Bawshar' AND type = 'city';
UPDATE locations SET latitude = 23.6714, longitude = 58.1893 WHERE name_en = 'Seeb' AND type = 'city';
UPDATE locations SET latitude = 23.5106, longitude = 58.4700 WHERE name_en = 'Al Amarat' AND type = 'city';
UPDATE locations SET latitude = 23.2567, longitude = 58.8994 WHERE name_en = 'Quriyat' AND type = 'city';

-- Dhofar Governorate
UPDATE locations SET latitude = 17.0151, longitude = 54.0924 WHERE name_en = 'Salalah' AND type = 'city';
UPDATE locations SET latitude = 17.0378, longitude = 54.4094 WHERE name_en = 'Taqah' AND type = 'city';
UPDATE locations SET latitude = 16.9917, longitude = 54.6917 WHERE name_en = 'Mirbat' AND type = 'city';
UPDATE locations SET latitude = 16.7553, longitude = 53.3961 WHERE name_en = 'Rakhyut' AND type = 'city';
UPDATE locations SET latitude = 17.6667, longitude = 54.0167 WHERE name_en = 'Thumrait' AND type = 'city';
UPDATE locations SET latitude = 16.6917, longitude = 53.1500 WHERE name_en = 'Dalkut' AND type = 'city';
UPDATE locations SET latitude = 18.0167, longitude = 52.8833 WHERE name_en = 'Al Mazyunah' AND type = 'city';
UPDATE locations SET latitude = 18.9833, longitude = 54.0333 WHERE name_en = 'Maqshin' AND type = 'city';
UPDATE locations SET latitude = 17.0000, longitude = 55.2333 WHERE name_en = 'Shalim and the Hallaniyat Islands' AND type = 'city';
UPDATE locations SET latitude = 17.0470, longitude = 54.7810 WHERE name_en = 'Sadah' AND type = 'city';

-- Al Dakhiliyah Governorate
UPDATE locations SET latitude = 22.9333, longitude = 57.5333 WHERE name_en = 'Nizwa' AND type = 'city';
UPDATE locations SET latitude = 22.9628, longitude = 57.2981 WHERE name_en = 'Bahla' AND type = 'city';
UPDATE locations SET latitude = 22.8653, longitude = 57.4603 WHERE name_en = 'Manah' AND type = 'city';
UPDATE locations SET latitude = 23.0675, longitude = 57.2847 WHERE name_en = 'Al Hamra' AND type = 'city';
UPDATE locations SET latitude = 22.3822, longitude = 57.5272 WHERE name_en = 'Adam' AND type = 'city';
UPDATE locations SET latitude = 23.4089, longitude = 58.1264 WHERE name_en = 'Bidbid' AND type = 'city';
UPDATE locations SET latitude = 23.3069, longitude = 57.9833 WHERE name_en = 'Samail' AND type = 'city';
UPDATE locations SET latitude = 22.9367, longitude = 57.7678 WHERE name_en = 'Izki' AND type = 'city';
UPDATE locations SET latitude = 23.0778, longitude = 57.3764 WHERE name_en = 'Jabal Al Akhdar' AND type = 'city';

-- North Al Batinah Governorate
UPDATE locations SET latitude = 24.3461, longitude = 56.7339 WHERE name_en = 'Sohar' AND type = 'city';
UPDATE locations SET latitude = 24.7444, longitude = 56.4600 WHERE name_en = 'Shinas' AND type = 'city';
UPDATE locations SET latitude = 24.5200, longitude = 56.5542 WHERE name_en = 'Liwa' AND type = 'city';
UPDATE locations SET latitude = 24.1703, longitude = 56.8853 WHERE name_en = 'Saham' AND type = 'city';
UPDATE locations SET latitude = 23.9700, longitude = 57.0900 WHERE name_en = 'Al Khaburah' AND type = 'city';
UPDATE locations SET latitude = 23.8500, longitude = 57.4333 WHERE name_en = 'Al Suwaiq' AND type = 'city';

-- South Al Batinah Governorate
UPDATE locations SET latitude = 23.3906, longitude = 57.4242 WHERE name_en = 'Rustaq' AND type = 'city';
UPDATE locations SET latitude = 23.2997, longitude = 57.5278 WHERE name_en = 'Al Awabi' AND type = 'city';
UPDATE locations SET latitude = 23.3911, longitude = 57.8306 WHERE name_en = 'Nakhal' AND type = 'city';
UPDATE locations SET latitude = 23.6794, longitude = 57.8872 WHERE name_en = 'Barka' AND type = 'city';
UPDATE locations SET latitude = 23.4667, longitude = 57.7167 WHERE name_en = 'Wadi Al Maawil' AND type = 'city';
UPDATE locations SET latitude = 23.7353, longitude = 57.6408 WHERE name_en = 'Al Musannah' AND type = 'city';

-- North Al Sharqiyah Governorate
UPDATE locations SET latitude = 22.6917, longitude = 58.5333 WHERE name_en = 'Ibra' AND type = 'city';
UPDATE locations SET latitude = 22.5667, longitude = 58.0167 WHERE name_en = 'Al Mudhaibi' AND type = 'city';
UPDATE locations SET latitude = 22.4500, longitude = 58.8000 WHERE name_en = 'Bidiyah' AND type = 'city';
UPDATE locations SET latitude = 22.5672, longitude = 58.4833 WHERE name_en = 'Al Qabil' AND type = 'city';
UPDATE locations SET latitude = 22.6058, longitude = 59.0542 WHERE name_en = 'Wadi Bani Khalid' AND type = 'city';
UPDATE locations SET latitude = 22.9500, longitude = 58.7833 WHERE name_en = 'Dima Wa Al Taaiyeen' AND type = 'city';

-- South Al Sharqiyah Governorate
UPDATE locations SET latitude = 22.5667, longitude = 59.5289 WHERE name_en = 'Sur' AND type = 'city';
UPDATE locations SET latitude = 22.2167, longitude = 59.1833 WHERE name_en = 'Al Kamil Wa Al Wafi' AND type = 'city';
UPDATE locations SET latitude = 22.0167, longitude = 59.2167 WHERE name_en = 'Jalan Bani Bu Ali' AND type = 'city';
UPDATE locations SET latitude = 22.0083, longitude = 59.3000 WHERE name_en = 'Jalan Bani Bu Hassan' AND type = 'city';
UPDATE locations SET latitude = 20.5667, longitude = 58.8833 WHERE name_en = 'Masirah' AND type = 'city';

-- Al Dhahirah Governorate
UPDATE locations SET latitude = 23.2250, longitude = 56.5164 WHERE name_en = 'Ibri' AND type = 'city';
UPDATE locations SET latitude = 23.5833, longitude = 56.5333 WHERE name_en = 'Yanqul' AND type = 'city';
UPDATE locations SET latitude = 23.3333, longitude = 56.2333 WHERE name_en = 'Dhank' AND type = 'city';

-- Al Buraimi Governorate
UPDATE locations SET latitude = 24.2500, longitude = 55.8333 WHERE name_en = 'Al Buraimi' AND type = 'city';
UPDATE locations SET latitude = 24.4167, longitude = 55.9833 WHERE name_en = 'Mahdah' AND type = 'city';
UPDATE locations SET latitude = 24.0667, longitude = 55.8500 WHERE name_en = 'Al Sunaynah' AND type = 'city';

-- Al Wusta Governorate
UPDATE locations SET latitude = 19.9500, longitude = 56.2833 WHERE name_en = 'Haima' AND type = 'city';
UPDATE locations SET latitude = 19.6591, longitude = 57.7042 WHERE name_en = 'Duqm' AND type = 'city';
UPDATE locations SET latitude = 20.1000, longitude = 58.2500 WHERE name_en = 'Mahout' AND type = 'city';
UPDATE locations SET latitude = 20.8333, longitude = 56.2833 WHERE name_en = 'Al Jazir' AND type = 'city';

-- Musandam Governorate
UPDATE locations SET latitude = 26.1700, longitude = 56.2500 WHERE name_en = 'Khasab' AND type = 'city';
UPDATE locations SET latitude = 25.6167, longitude = 56.2667 WHERE name_en = 'Dibba' AND type = 'city';
UPDATE locations SET latitude = 26.0833, longitude = 56.1667 WHERE name_en = 'Bukha' AND type = 'city';
UPDATE locations SET latitude = 25.2917, longitude = 56.3333 WHERE name_en = 'Madha' AND type = 'city';

-- Verify: count locations with coordinates
-- SELECT type, COUNT(*) as total, COUNT(latitude) as with_coords FROM locations GROUP BY type;
