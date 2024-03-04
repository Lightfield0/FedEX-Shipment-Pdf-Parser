import sys, qdarktheme
from PyQt6.QtWidgets import ( QApplication, QWidget, QVBoxLayout, QComboBox, QTextEdit, QPushButton,
                            QFileDialog, QLabel, QGroupBox, QHBoxLayout, QSpacerItem,
                            QSizePolicy, QDateEdit, QTabWidget, QMessageBox
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QDate
import re
import pdfplumber
import pandas as pd
import os
from datetime import datetime



def path_(yol):
    if hasattr(sys, '_MEIPASS'):
        path = os.path.join(sys._MEIPASS, yol)
    else:
        path = yol
    return path


def parse_currency(value):
    if isinstance(value, str):
        # "TL" metnini kaldır ve binlik ayırıcı olan noktaları kaldır
        value = value.replace("TL", "").replace(".", "")

        # Ondalık ayırıcı olan virgülü noktaya çevir
        value = value.replace(",", ".")

        try:
            # Sayısal bir değere dönüştür
            return float(value)
        except ValueError:
            return 0.0  # Dönüşüm başarısız olursa 0.0 döndür
    return value


def extract_usd_exchange_rate(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                match = re.search(r'USD:(\d+\.\d+)', text)
                if match:
                    return match.group(1)
    return None  # Dolar kuru bulunamadı


def extract_tables_with_pdfplumber(pdf_path):
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                all_tables.append(table)
    return all_tables

def extract_country_and_date(detail):
    # Regular expression pattern to extract country and date
    country_pattern = r'Ulke:\s*([A-Z]{2})'
    date_pattern = r'Delivery Date:\s*([\d\/]+)'

    # Search for country
    country_match = re.search(country_pattern, detail, re.IGNORECASE)
    country = country_match.group(1) if country_match else None

    # Search for delivery date
    date_match = re.search(date_pattern, detail, re.IGNORECASE)
    delivery_date = None
    if date_match:
        try:
            delivery_date = datetime.strptime(date_match.group(1), '%m/%d/%Y').strftime('%Y-%m-%d')
        except ValueError:
            pass  # Invalid date format

    return country, delivery_date

def convert_to_dataframe(data, usd_rate, file_name):
    rows = []
    for row in data[2:]:  # İlk satır başlıklar olabilir, atla
        row = list(filter(None, row))  # None olanları kaldır
        print(row)
        if len(row) >= 6:  # Beklenen sütun sayısını kontrol et
            try:
                # Satırdan gerekli bilgileri çıkar
                tarih_ve_gonderi_no = row[0].split('\n')
                tarih = tarih_ve_gonderi_no[0] if len(tarih_ve_gonderi_no) > 0 else None
                gonderi_no = tarih_ve_gonderi_no[1] if len(tarih_ve_gonderi_no) > 1 else None
                cikis_yeri = row[1].split('\n')[0]
                teslimat_detayi = row[2]
                country, delivery_date = extract_country_and_date(teslimat_detayi)
                agirlik = row[3]

                tutar = row[5]

                row_data = {
                    "Tarih": tarih,
                    "Gönderi No": gonderi_no,
                    "Çıkış Yeri": cikis_yeri,
                    "Teslimat Detayı": teslimat_detayi,
                    "Ülke": country,
                    "Ağırlık (Kg/Gr)": agirlik,
                    "Dolar Kuru": usd_rate,
                    "Tutar": tutar,
                    "Dosya Adı": file_name,  # Dosya adını ekleyin
                }
                rows.append(row_data)
            except IndexError:
                print(f"Satır formatı hatalı: {row}")
                continue

    return pd.DataFrame(rows)

def convert_all_tables_to_dataframe(tables, usd_rate, file_path):
    file_name = os.path.basename(file_path)  # Dosya adını al
    all_dfs = []
    for table in tables:
        df = convert_to_dataframe(table, usd_rate, file_name)
        all_dfs.append(df)
    return pd.concat(all_dfs, ignore_index=True)


class PaketBilgiArayuzu(QWidget):
    def __init__(self):
        super().__init__()
        self.df = pd.DataFrame()
        self.initUI()

    def initUI(self):
        # Ana düzeni oluştur
        mainLayout = QVBoxLayout(self)

        # Sekme widget'ı oluştur
        tabWidget = QTabWidget()

        # PDF Yükleme sekmesi
        pdfTab = self.createPdfTab()
        tabWidget.addTab(pdfTab, "Kargo Analizi")

        # Fiyat Sorgulama sekmesi
        fiyatTab = self.createFiyatTab()
        tabWidget.addTab(fiyatTab, "Fiyat Sorgulama")

        # Sekmeleri ana düzene ekle
        mainLayout.addWidget(tabWidget)

        self.setWindowTitle('Kargo Analiz Paneli')
        self.setWindowIcon(QIcon(path_('logo.png')))

        self.csvYukle()

    def createPdfTab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # PDF Load Section
        loadGroupBox = QGroupBox("PDF Yükleme")
        loadLayout = QHBoxLayout()

        self.yukleButton = QPushButton('PDF Yükle')
        self.yukleButton.clicked.connect(self.pdfYukle)
        loadLayout.addWidget(self.yukleButton)

        loadGroupBox.setLayout(loadLayout)
        layout.addWidget(loadGroupBox)

        # Country Filter Section
        countryGroupBox = QGroupBox("Ülke Filtreleme")
        countryLayout = QHBoxLayout()

        countryLabel = QLabel("Ülke:")
        self.UlkeCombo = QComboBox()
        self.UlkeCombo.currentTextChanged.connect(self.ulkeSecildi)
        countryLayout.addWidget(countryLabel)
        countryLayout.addWidget(self.UlkeCombo)

        countryGroupBox.setLayout(countryLayout)
        layout.addWidget(countryGroupBox)

        # Departure Filter Section
        departureGroupBox = QGroupBox("Çıkış Yeri Filtreleme")
        departureLayout = QHBoxLayout()

        departureLabel = QLabel("Çıkış Yeri:")
        self.CikisYeriCombo = QComboBox()
        self.CikisYeriCombo.currentTextChanged.connect(self.CikisYeriSecildi)
        departureLayout.addWidget(departureLabel)
        departureLayout.addWidget(self.CikisYeriCombo)

        departureGroupBox.setLayout(departureLayout)
        layout.addWidget(departureGroupBox)

        # Tarih Aralığı Filtreleme Bölümü
        tarihAraligiGroupBox = QGroupBox("Tarih Aralığı Filtreleme")
        tarihAraligiLayout = QHBoxLayout()

        self.baslangicTarihCombo = QComboBox()
        self.bitisTarihCombo = QComboBox()

        tarihAraligiLayout.addWidget(QLabel("Başlangıç Tarihi:"))
        tarihAraligiLayout.addWidget(self.baslangicTarihCombo)
        tarihAraligiLayout.addWidget(QLabel("Bitiş Tarihi:"))
        tarihAraligiLayout.addWidget(self.bitisTarihCombo)

        self.tarihAraligiFilterButton = QPushButton('Filtrele')
        self.tarihAraligiFilterButton.clicked.connect(self.filterByDateRange)

        tarihAraligiLayout.addWidget(self.tarihAraligiFilterButton)

        tarihAraligiGroupBox.setLayout(tarihAraligiLayout)
        layout.addWidget(tarihAraligiGroupBox)

        # Text Area
        self.textArea = QTextEdit()
        self.textArea.setReadOnly(True)
        layout.addWidget(self.textArea)

        tab.setLayout(layout)
        return tab
    
    def createFiyatTab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # Ülke Filtreleme Bölümü
        ulkeGroupBox = QGroupBox("Ülke Filtreleme")
        ulkeLayout = QHBoxLayout()
        self.fiyatUlkeCombo = QComboBox()
        ulkeLayout.addWidget(QLabel("Ülke:"))
        ulkeLayout.addWidget(self.fiyatUlkeCombo)
        ulkeGroupBox.setLayout(ulkeLayout)
        layout.addWidget(ulkeGroupBox)

        # Ağırlık Filtreleme Bölümü
        agirlikGroupBox = QGroupBox("Ağırlık Filtreleme")
        agirlikLayout = QHBoxLayout()
        self.fiyatAgirlikCombo = QComboBox()
        agirlikLayout.addWidget(QLabel("Ağırlık (Kg/Gr):"))
        agirlikLayout.addWidget(self.fiyatAgirlikCombo)
        agirlikGroupBox.setLayout(agirlikLayout)
        layout.addWidget(agirlikGroupBox)

        # Tarih Aralığı Filtreleme Bölümü
        tarihAraligiGroupBox = QGroupBox("Tarih Aralığı Filtreleme")
        tarihAraligiLayout = QHBoxLayout()

        self.fiyatBaslangicTarihCombo = QComboBox()
        self.fiyatBitisTarihCombo = QComboBox()


        tarihAraligiLayout.addWidget(QLabel("Başlangıç Tarihi:"))
        tarihAraligiLayout.addWidget(self.fiyatBaslangicTarihCombo)
        tarihAraligiLayout.addWidget(QLabel("Bitiş Tarihi:"))
        tarihAraligiLayout.addWidget(self.fiyatBitisTarihCombo)
        tarihAraligiGroupBox.setLayout(tarihAraligiLayout)
        layout.addWidget(tarihAraligiGroupBox)

        # Fiyat Sorgula Butonu
        self.fiyatSorgulaButton = QPushButton('Fiyat Sorgula')
        self.fiyatSorgulaButton.clicked.connect(self.fiyatSorgula)
        layout.addWidget(self.fiyatSorgulaButton)

        # Sonuçların Görüntüleneceği Metin Alanı
        self.fiyatSonucArea = QTextEdit()
        self.fiyatSonucArea.setReadOnly(True)
        layout.addWidget(self.fiyatSonucArea)

        tab.setLayout(layout)
        return tab

    def uygun_formati_kontrol_et(self, row):
        # cikis_yeri_pattern = r'^TR - \w+ \w+$'  # Örnek: "TR - KAYSERI ALP"
        ulke_pattern = r'^[A-Z]{2}$'  # Örnek: "US", "DE"
        agirlik_pattern = r'^\d+,\d+$|^\d+$'  # Örnek: "21", "0,5"

        # cikis_yeri_match = re.match(cikis_yeri_pattern, str(row['Çıkış Yeri']))
        ulke_match = re.match(ulke_pattern, str(row['Ülke']))
        agirlik_match = re.match(agirlik_pattern, str(row['Ağırlık (Kg/Gr)']))

        return ulke_match is not None and agirlik_match is not None

    def csvYukle(self):
        try:
            self.df = pd.read_csv('paket_bilgileri.csv')
            
            # DataFrame'i filtrele
            self.df = self.df[self.df.apply(self.uygun_formati_kontrol_et, axis=1)]

            self.updateComboBoxes()
            self.filtreleVeGoster()
        except FileNotFoundError:
            self.textArea.setText("CSV dosyası bulunamadı.")
        except Exception as e:
            self.textArea.setText(f"Hata: {e}")


    def updateComboBoxes(self):
        self.updateCombo(self.UlkeCombo, 'Ülke', r'^[A-Z]{2}$')  # Ülke kodu için regex
        self.updateCombo(self.fiyatUlkeCombo, 'Ülke', r'^[A-Z]{2}$')
        self.updateCombo(self.fiyatAgirlikCombo, 'Ağırlık (Kg/Gr)', None)  # Sayısal değer için regex
        self.updateCombo(self.CikisYeriCombo, 'Çıkış Yeri', None)  # Herhangi bir regex yok
        self.updateDateComboBoxes(self.baslangicTarihCombo, self.bitisTarihCombo)
        self.updateDateComboBoxes(self.fiyatBaslangicTarihCombo, self.fiyatBitisTarihCombo)

    def updateCombo(self, combo, column_name, regex_pattern):
        unique_items = set(self.df[column_name].dropna().astype(str))
        if regex_pattern:
            pattern = re.compile(regex_pattern)
            unique_items = {item for item in unique_items if pattern.match(item)}
        combo.clear()
        combo.addItems(['Hepsi'] + sorted(unique_items))

    def updateDateComboBoxes(self, baslangicCombo, bitisCombo):
        try:
            # Tarihleri datetime nesnesine dönüştür
            unique_dates = pd.to_datetime(self.df['Tarih'].dropna().unique(), dayfirst=True, errors='coerce').dropna()
            # Tarihleri sırala ve formatla
            formatted_dates = [date.strftime('%d.%m.%Y') for date in sorted(unique_dates)]
            baslangicCombo.clear()
            bitisCombo.clear()
            baslangicCombo.addItems(['Hepsi'] + formatted_dates)
            bitisCombo.addItems(['Hepsi'] + formatted_dates)
        except Exception as e:
            print(f"Tarih güncelleme hatası: {e}")


    def pdfYukle(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "PDF Dosyası Seç", "", "PDF Dosyaları (*.pdf)")
        if file_name:
            # Dosya adını temizleme ve sadece dosya adını alma
            clean_file_name = os.path.basename(file_name)

            # 'Dosya Adı' sütununun self.df içinde olup olmadığını kontrol etme
            if 'Dosya Adı' in self.df.columns:
                
                if clean_file_name in self.df['Dosya Adı'].values:
                    # Dosya adı zaten varsa uyarı mesajı göster
                    self.showErrorMessage(f"'{clean_file_name}' isimli dosya zaten yüklü.")
                else:
                    self.veriIsle(file_name)

            else:
                # Dosya adı veritabanında yoksa veri işleme fonksiyonunu çağır
                self.veriIsle(file_name)

    def showErrorMessage(self, message):
        QMessageBox.warning(self, "Hata", message)

    def veriIsle(self, pdf_path):
        tables = extract_tables_with_pdfplumber(pdf_path)
        usd_rate = extract_usd_exchange_rate(pdf_path)  # Dolar kuru çıkar
        print(tables)
        new_df = convert_all_tables_to_dataframe(tables, usd_rate, pdf_path)  # Örnek için tables[2] kullanılıyor
        self.df = pd.concat([self.df, new_df])
        self.updateComboBoxes()
        
        self.filtreleVeGoster()

        self.df.to_csv('paket_bilgileri.csv', index=False)  # DataFrame'i CSV olarak kaydet

    def ulkeSecildi(self):
            self.filtreleVeGoster()

    def CikisYeriSecildi(self):
        self.filtreleVeGoster()
    
    def filtreleVeGoster(self):
        secili_ulke = self.UlkeCombo.currentText()
        secili_cikis_yeri = self.CikisYeriCombo.currentText()
        baslangic_tarihi = self.baslangicTarihCombo.currentText()
        bitis_tarihi = self.bitisTarihCombo.currentText()

        filtered_df = self.df

        if secili_ulke != 'Hepsi':
            filtered_df = filtered_df[filtered_df['Ülke'] == secili_ulke]

        if secili_cikis_yeri != 'Hepsi':
            filtered_df = filtered_df[filtered_df['Çıkış Yeri'] == secili_cikis_yeri]

        if baslangic_tarihi != 'Hepsi' and bitis_tarihi != 'Hepsi':
            filtered_df = filtered_df[(filtered_df['Tarih'] >= baslangic_tarihi) & (filtered_df['Tarih'] <= bitis_tarihi)]

        if not filtered_df.empty:
            self.displayData(filtered_df)
        else:
            self.textArea.setText("Belirtilen kriterlere uygun kayıt bulunamadı.")


    def filterByDateRange(self):
        self.filtreleVeGoster()

    def displayData(self, df):
        # Ağırlıklara göre paket sayılarını hesaplama
        agirlik_sayilari = df['Ağırlık (Kg/Gr)'].value_counts()
        agirlik_mesaji = '\n'.join([f'{agirlik} kg: {sayi} paket' for agirlik, sayi in agirlik_sayilari.items()])

        # Toplam paket sayısını hesaplama
        toplam_paket_sayisi = df.shape[0]  # Satır sayısı toplam paket sayısını verir
        toplam_mesaj = f"Toplam Paket Sayısı: {toplam_paket_sayisi}\n\n"

        # Sonuçları metin alanında gösterme
        self.textArea.setText(toplam_mesaj + agirlik_mesaji)

    def fiyatSorgula(self):
        secili_ulke = self.fiyatUlkeCombo.currentText()
        secili_agirlik = self.fiyatAgirlikCombo.currentText()
        baslangic_tarihi = self.fiyatBaslangicTarihCombo.currentText()
        bitis_tarihi = self.fiyatBitisTarihCombo.currentText()

        # Filtreleme işlemi
        filtered_df = self.df
        if secili_ulke != 'Hepsi':
            filtered_df = filtered_df[filtered_df['Ülke'] == secili_ulke]

        if secili_agirlik != 'Hepsi':
            filtered_df = filtered_df[filtered_df['Ağırlık (Kg/Gr)'] == secili_agirlik]
            print(filtered_df)

        if baslangic_tarihi != 'Hepsi' and bitis_tarihi != 'Hepsi':
            filtered_df = filtered_df[(filtered_df['Tarih'] >= baslangic_tarihi) & (filtered_df['Tarih'] <= bitis_tarihi)]

        # İlk kayıt üzerinden fiyat hesaplama işlemi
        if not filtered_df.empty:
            fiyat = self.hesaplaFiyat(filtered_df.iloc[0])
            self.fiyatSonucArea.setText(f'Fiyat: {fiyat:.2f} $')
        else:
            self.fiyatSonucArea.setText("Belirtilen kriterlere uygun kayıt bulunamadı.")

    def hesaplaFiyat(self, row):
        tutar = parse_currency(row['Tutar'])  # Tutarı işle
        dolar_kuru = row['Dolar Kuru']  # Dolar Kuru'nu al
        return (tutar / dolar_kuru) * 1.0235  # Hesaplama formülü

if __name__ == '__main__':
    app = QApplication(sys.argv)
    qdarktheme.enable_hi_dpi()
    qdarktheme.setup_theme()
    ex = PaketBilgiArayuzu()
    ex.show()
    sys.exit(app.exec())
