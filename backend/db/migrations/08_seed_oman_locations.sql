-- Migration to fetch Oman Governorates and Cities
-- Ensure locations table exists (handled in 04_add_locations.sql)

DO $$ 
DECLARE 
    muscat_id UUID;
    dhofar_id UUID;
    dakhiliyah_id UUID;
    north_batinah_id UUID;
    south_batinah_id UUID;
    north_sharqiyah_id UUID;
    south_sharqiyah_id UUID;
    dhahirah_id UUID;
    buraimi_id UUID;
    wusta_id UUID;
    musandam_id UUID;
BEGIN

    -- 1. Muscat Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('Muscat Governorate', 'محافظة مسقط', 'state', true) 
    RETURNING id INTO muscat_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Muscat', 'مسقط', 'city', muscat_id, true),
    ('Muttrah', 'مطرح', 'city', muscat_id, true),
    ('Bawshar', 'بوشر', 'city', muscat_id, true),
    ('Seeb', 'السيب', 'city', muscat_id, true),
    ('Al Amarat', 'العامرات', 'city', muscat_id, true),
    ('Quriyat', 'قريات', 'city', muscat_id, true);

    -- 2. Dhofar Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('Dhofar Governorate', 'محافظة ظفار', 'state', true) 
    RETURNING id INTO dhofar_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Salalah', 'صلالة', 'city', dhofar_id, true),
    ('Taqah', 'طاقة', 'city', dhofar_id, true),
    ('Mirbat', 'مرباط', 'city', dhofar_id, true),
    ('Rakhyut', 'رخيوت', 'city', dhofar_id, true),
    ('Thumrait', 'ثمريت', 'city', dhofar_id, true),
    ('Dalkut', 'ضلكوت', 'city', dhofar_id, true),
    ('Al Mazyunah', 'المزيونة', 'city', dhofar_id, true),
    ('Maqshin', 'مقشن', 'city', dhofar_id, true),
    ('Shalim and the Hallaniyat Islands', 'شليم وجزر الحلانيات', 'city', dhofar_id, true),
    ('Sadah', 'سدح', 'city', dhofar_id, true);

    -- 3. Al Dakhiliyah Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('Al Dakhiliyah Governorate', 'محافظة الداخلية', 'state', true) 
    RETURNING id INTO dakhiliyah_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Nizwa', 'نزوى', 'city', dakhiliyah_id, true),
    ('Bahla', 'بهلاء', 'city', dakhiliyah_id, true),
    ('Manah', 'منح', 'city', dakhiliyah_id, true),
    ('Al Hamra', 'الحمراء', 'city', dakhiliyah_id, true),
    ('Adam', 'أدم', 'city', dakhiliyah_id, true),
    ('Bidbid', 'بدبد', 'city', dakhiliyah_id, true),
    ('Samail', 'سمائل', 'city', dakhiliyah_id, true),
    ('Izki', 'إزكي', 'city', dakhiliyah_id, true),
    ('Jabal Al Akhdar', 'الجبل الأخضر', 'city', dakhiliyah_id, true);

    -- 4. North Al Batinah Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('North Al Batinah Governorate', 'محافظة شمال الباطنة', 'state', true) 
    RETURNING id INTO north_batinah_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Sohar', 'صحار', 'city', north_batinah_id, true),
    ('Shinas', 'شناص', 'city', north_batinah_id, true),
    ('Liwa', 'لوى', 'city', north_batinah_id, true),
    ('Saham', 'صحم', 'city', north_batinah_id, true),
    ('Al Khaburah', 'الخابورة', 'city', north_batinah_id, true),
    ('Al Suwaiq', 'السويق', 'city', north_batinah_id, true);

    -- 5. South Al Batinah Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('South Al Batinah Governorate', 'محافظة جنوب الباطنة', 'state', true) 
    RETURNING id INTO south_batinah_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Rustaq', 'الرستاق', 'city', south_batinah_id, true),
    ('Al Awabi', 'العوابي', 'city', south_batinah_id, true),
    ('Nakhal', 'نخل', 'city', south_batinah_id, true),
    ('Barka', 'بركاء', 'city', south_batinah_id, true),
    ('Wadi Al Maawil', 'وادي المعاول', 'city', south_batinah_id, true),
    ('Al Musannah', 'المصنعة', 'city', south_batinah_id, true);

    -- 6. North Al Sharqiyah Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('North Al Sharqiyah Governorate', 'محافظة شمال الشرقية', 'state', true) 
    RETURNING id INTO north_sharqiyah_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Ibra', 'إبراء', 'city', north_sharqiyah_id, true),
    ('Al Mudhaibi', 'المضيبي', 'city', north_sharqiyah_id, true),
    ('Bidiyah', 'بدية', 'city', north_sharqiyah_id, true),
    ('Al Qabil', 'القابل', 'city', north_sharqiyah_id, true),
    ('Wadi Bani Khalid', 'وادي بني خالد', 'city', north_sharqiyah_id, true),
    ('Dima Wa Al Taaiyeen', 'دماء والطائيين', 'city', north_sharqiyah_id, true);

    -- 7. South Al Sharqiyah Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('South Al Sharqiyah Governorate', 'محافظة جنوب الشرقية', 'state', true) 
    RETURNING id INTO south_sharqiyah_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Sur', 'صور', 'city', south_sharqiyah_id, true),
    ('Al Kamil Wa Al Wafi', 'الكامل والوافي', 'city', south_sharqiyah_id, true),
    ('Jalan Bani Bu Ali', 'جعلان بني بو علي', 'city', south_sharqiyah_id, true),
    ('Jalan Bani Bu Hassan', 'جعلان بني بو حسن', 'city', south_sharqiyah_id, true),
    ('Masirah', 'مصيرة', 'city', south_sharqiyah_id, true);

    -- 8. Al Dhahirah Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('Al Dhahirah Governorate', 'محافظة الظاهرة', 'state', true) 
    RETURNING id INTO dhahirah_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Ibri', 'عبري', 'city', dhahirah_id, true),
    ('Yanqul', 'ينقل', 'city', dhahirah_id, true),
    ('Dhank', 'ضنك', 'city', dhahirah_id, true);

    -- 9. Al Buraimi Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('Al Buraimi Governorate', 'محافظة البريمي', 'state', true) 
    RETURNING id INTO buraimi_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Al Buraimi', 'البريمي', 'city', buraimi_id, true),
    ('Mahdah', 'محضة', 'city', buraimi_id, true),
    ('Al Sunaynah', 'السنينة', 'city', buraimi_id, true);

    -- 10. Al Wusta Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('Al Wusta Governorate', 'محافظة الوسطى', 'state', true) 
    RETURNING id INTO wusta_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Haima', 'هيماء', 'city', wusta_id, true),
    ('Duqm', 'الدقم', 'city', wusta_id, true),
    ('Mahout', 'محوت', 'city', wusta_id, true),
    ('Al Jazir', 'الجازر', 'city', wusta_id, true);

    -- 11. Musandam Governorate
    INSERT INTO locations (name_en, name_ar, type, is_active) 
    VALUES ('Musandam Governorate', 'محافظة مسندم', 'state', true) 
    RETURNING id INTO musandam_id;

    INSERT INTO locations (name_en, name_ar, type, parent_id, is_active) VALUES 
    ('Khasab', 'خصب', 'city', musandam_id, true),
    ('Dibba', 'دبا', 'city', musandam_id, true),
    ('Bukha', 'بخاء', 'city', musandam_id, true),
    ('Madha', 'مدحاء', 'city', musandam_id, true);

END $$;
