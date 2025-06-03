# YokTez MCP: YÖK Ulusal Tez Merkezi için MCP Sunucusu

[![Star History Chart](https://api.star-history.com/svg?repos=saidsurucu/yoktez-mcp&type=Date)](https://www.star-history.com/#saidsurucu/yoktez-mcp&Date)

Bu proje, Yükseköğretim Kurulu (YÖK) Ulusal Tez Merkezi'ne erişimi kolaylaştıran bir [FastMCP](https://gofastmcp.com/) sunucusu oluşturur. Bu sayede, YÖK Tez Merkezi'nden tez arama ve tezlerin PDF içeriklerini Markdown formatında getirme işlemleri, Model Context Protocol (MCP) destekleyen LLM (Büyük Dil Modeli) uygulamaları (örneğin Claude Desktop veya [5ire](https://5ire.app)) ve diğer istemciler tarafından araç (tool) olarak kullanılabilir hale gelir.

![YÖK Tez MCP Örneği](./yoktez_ornek.png)
*(Kendi örnek görselinizle değiştirin)*

🎯 **Temel Özellikler**

* YÖK Ulusal Tez Merkezi'ne programatik erişim için standart bir MCP arayüzü.
* Aşağıdaki yetenekler:
    * **Detaylı Tez Arama:** Başlık, yazar, danışman, üniversite, enstitü, anabilim/bilim dalı, tez türü, yıl aralığı, izin durumu, tez numarası, konu, dizin ve özet metni gibi çeşitli kriterlere göre tez arama.
    * **Tez Belgesi Getirme:** Belirli bir tezin PDF içeriğini, PDF sayfa bazında, işlenmiş Markdown formatında getirme.
    * **Metadata Çıkarımı:** Tez detay sayfalarından başlık, yazar, yıl, özet gibi önemli üst verilerin çıkarılması.
    * **PDF İzin Kontrolü:** Erişilemeyen veya yayın izni olmayan tezler için uygun bildirim.
* Karar metinlerinin LLM'ler tarafından daha kolay işlenebilmesi için Markdown formatına çevrilmesi.
* Claude Desktop uygulaması ile `fastmcp install` komutu kullanılarak kolay entegrasyon.
* YokTez MCP artık [5ire](https://5ire.app) gibi Claude Desktop haricindeki MCP istemcilerini de destekliyor!

---
🚀 **Claude Haricindeki Modellerle Kullanmak İçin Çok Kolay Kurulum (Örnek: 5ire için)**

Bu bölüm, YokTez MCP aracını 5ire gibi Claude Desktop dışındaki MCP istemcileriyle kullanmak isteyenler içindir.

* **Windows Kullanıcıları:** Eğer Python kurulu değilse, [python.org/downloads/windows/](https://www.python.org/downloads/windows/) adresinden Python 3.11'in uygun bir sürümünü indirip kurun. Kurulum sırasında "**Add Python to PATH**" (Python'ı PATH'e ekle) seçeneğini işaretlemeyi unutmayın.
* **Windows Kullanıcıları:** Bilgisayarınıza [git](https://git-scm.com/downloads/win) yazılımını indirip kurun. "Git for Windows/x64 Setup" seçeneğini indirmelisiniz.
* **Windows Kullanıcıları:** Bir CMD penceresi açın ve içine bu komutu yapıştırıp çalıştırın. Kurulumun bitmesini bekleyin: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
* **Mac/Linux Kullanıcıları:** Bir Terminal penceresi açın ve içine bu komutu yapıştırıp çalıştırın. Kurulumun bitmesini bekleyin: `curl -LsSf https://astral.sh/uv/install.sh | sh`
* İşletim sisteminize uygun [5ire](https://5ire.app) MCP istemcisini indirip kurun.
* 5ire'ı açın. **Workspace -> Providers** menüsünden kullanmak istediğiniz LLM servisinin API anahtarını girin. Kendi makinenizde çalıştırdığınız yerel modelleri de buradan ayarlayabilirsiniz.
* **Tools** menüsüne girin. **+Local** yazan butona basın.
    * **Tool Key:** `yoktezmcp` (veya tercih ettiğiniz bir anahtar)
    * **Name:** `YokTez MCP`
    * **Command:** Bu komut, `yoktez_mcp_server.py` dosyasını nasıl çalıştırdığınıza bağlıdır. Eğer `yoktez-mcp` projesini klonladıysanız ve bağımlılıkları bir sanal ortama kurduysanız:
        * Örnek Komut (Python ile çalıştırma): `python`
        * Arguments: `/tam/proje/yolunuz/yoktez-mcp/yoktez_mcp_server.py` (Bu yolu kendi sisteminizdeki doğru yolla değiştirin. 5ire'ın bu scripti ve bağımlılıklarını bulabileceği bir ortamda olması gerekir.)
        * Veya eğer `fastmcp run` ile çalıştırıyorsanız:
            * Command: `fastmcp`
            * Arguments: `run /tam/proje/yolunuz/yoktez-mcp/yoktez_mcp_server.py`
    * (Eğer projeyi `uvx --from git+https://github.com/saidsurucu/yoktez-mcp yoktez-mcp-cli-command` gibi bir yapıyla çalıştırılabilir hale getirdiyseniz, o komutu kullanın.)
    * **Save** butonuna basarak kaydedin.

![5ire YokTez MCP Ayarları](./5ire_yoktez_ayarlar.png)
*(Kendi 5ire ayar görselinizle değiştirin)*

* Şimdi **Tools** altında **YokTez MCP**'yi görüyor olmalısınız. Üzerine geldiğinizde yanda bir açma kapama düğmesi çıkacak, ona tıklayarak MCP sunucusunu etkinleştirin. Eğer kurulum adımlarını doğru yaptıysanız YokTez MCP yazısının yanında yeşil ışık yanacaktır.
* Artık istediğiniz LLM modelini kullanarak YokTez MCP ile konuşabilirsiniz.

---
📋 **Ön Gereksinimler**

Bu YokTez MCP aracını Claude Desktop ile kullanabilmek için öncelikle aşağıdaki yazılımların sisteminizde kurulu olması gerekmektedir:

1.  **Claude Desktop:** Henüz kurmadıysanız, [Claude Desktop web sitesinden](https://claude.ai/desktop) işletim sisteminize uygun sürümü indirip kurun.
2.  **Python Sürümü:** **Python 3.11** sürümü tavsiye edilir. Python 3.12 ve üzeri yeni sürümler, bazı bağımlılıklarda (özellikle `playwright`) belirli ortamlarda uyumluluk sorunlarına yol açabilir.
    * **Windows Kullanıcıları:** [python.org/downloads/windows/](https://www.python.org/downloads/windows/) adresinden Python 3.11'i kurun. Kurulum sırasında "**Add Python to PATH**" seçeneğini işaretleyin.
    * **macOS Kullanıcıları:** `python3 --version` ile kontrol edin. Gerekirse [python.org](https://www.python.org/downloads/macos/) veya Homebrew (`brew install python@3.11`) ile kurun.
    * **Linux Kullanıcıları:** `python3 --version` ile kontrol edin. Gerekirse dağıtımınızın paket yöneticisi ile Python 3.11'i kurun (örn: `sudo apt update && sudo apt install python3.11 python3.11-pip python3.11-venv`).
3.  **Paket Yöneticisi:** `pip` (Python ile birlikte gelir) veya tercihen `uv` ([Astral](https://astral.sh/uv) tarafından geliştirilen hızlı Python paket yöneticisi).
4.  **Playwright Tarayıcıları:** YokTez MCP, Playwright kullandığı için ilgili tarayıcıların (özellikle Chromium) kurulmuş olması gerekir.
    ```bash
    # Önce playwright kütüphanesini kurun (uv veya pip ile)
    # uv pip install playwright 
    # pip install playwright

    # Sonra tarayıcıları kurun
    playwright install --with-deps chromium 
    # '--with-deps' chromium için gerekli işletim sistemi bağımlılıklarını da kurmaya çalışır.
    ```
    `fastmcp install` komutu veya kolay kurulum script'leri genellikle `playwright` Python kütüphanesini kurar, ancak tarayıcıların ayrıca bu komutla kurulması gerekebilir.

---
🚀 **Kolay Kurulum Adımları (Claude Desktop için)**

Bu bölüm, YokTez MCP aracını Claude Desktop uygulamalarına hızlıca entegre etmek isteyen kullanıcılar içindir.

**Öncelikle Yapılması Gerekenler:**

1.  **Proje Dosyalarını İndirin:**
    * Bu GitHub deposunun ana sayfasına gidin.
    * Yeşil renkli "**<> Code**" düğmesine tıklayın.
    * Açılan menüden "**Download ZIP**" seçeneğini seçin.
    * İndirdiğiniz ZIP dosyasını bilgisayarınızda kolayca erişebileceğiniz bir klasöre çıkartın (örneğin, `Belgelerim` altında `yoktez-mcp` adında bir klasör).

Proje dosyalarını bilgisayarınıza aldıktan sonra, işletim sisteminize uygun kurulum script'ini çalıştırabilirsiniz. (Bu script'ler henüz projede bulunmamaktadır, ancak oluşturulursa aşağıdaki gibi kullanılabilirler.)

### Windows Kullanıcıları İçin (`install.bat` - *Eğer oluşturulursa*)
1.  Proje dosyalarını çıkarttığınız klasöre gidin.
2.  `install.bat` dosyasına çift tıklayarak çalıştırın.
3.  Script, gerekli araçları (`uv`, `fastmcp` CLI) kurmayı ve YokTez MCP'yi Claude Desktop'a entegre etmeyi deneyecektir.
4.  Kurulum sonrası Claude Desktop'ı yeniden başlatın.

### macOS ve Linux Kullanıcıları İçin (`install.sh` - *Eğer oluşturulursa*)
1.  Terminal ile proje dosyalarını çıkarttığınız klasöre gidin.
2.  Script'e çalıştırma izni verin: `chmod +x install.sh`
3.  Script'i çalıştırın: `./install.sh`
4.  Script, gerekli araçları kurmayı ve entegrasyonu yapmayı deneyecektir.
5.  Kurulum sonrası Claude Desktop'ı ve gerekirse terminalinizi yeniden başlatın.

### Python Script ile Kurulum (`install.py` - *Eğer oluşturulursa*)
1.  Terminal veya Komut İstemi ile proje klasörüne gidin.
2.  `python3 install.py` (veya `python install.py`) komutunu çalıştırın.

---
⚙️ **Gelişmiş Kurulum Adımları (Claude Desktop Entegrasyonu Odaklı)**

Claude Desktop uygulamasına yükleme yapabilmek için `uv` (önerilir) ve `fastmcp` komut satırı araçlarını kurmanız ve proje dosyalarını almanız gerekmektedir.

**1. `uv` Kurulumu (Önerilir)**
* **macOS ve Linux için:**
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
* **Windows için (PowerShell kullanarak):**
    ```powershell
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
    `uv --version` ile kurulumu doğrulayın.

**2. `fastmcp` Komut Satırı Aracının (CLI) Kurulumu**
* **`uv` kullanarak (önerilir):**
    ```bash
    uv pip install fastmcp
    ```
* **`pip` kullanarak (alternatif):**
    ```bash
    pip install fastmcp
    ```
    `fastmcp --version` ile kurulumu doğrulayın.

**3. Proje Dosyalarını Alın**
Bu YokTez MCP sunucusunun kaynak kodlarını bilgisayarınıza indirin:
```bash
git clone https://github.com/saidsurucu/yoktez-mcp.git
cd yoktez-mcp
```
(Bu README.md dosyasının ve `yoktez_mcp_server.py` script'inin bulunduğu dizine `cd` komutu ile geçmiş olacaksınız.)

**4. Sunucuya Özel Bağımlılıkların Bilinmesi**
Bu sunucunun (`yoktez_mcp_server.py`) çalışması için `requirements.txt` dosyasında listelenen Python kütüphanelerine ihtiyacı vardır:
```text
# requirements.txt (örnek içerik, projenizdekiyle eşleşmeli)
beautifulsoup4
httpx
markitdown[pdf]
playwright
pydantic
pypdf
ftfy
lxml
fastmcp 
# uv (uv genellikle ayrı kurulur, pip ile değil)
```
Eğer sunucuyu bağımsız geliştirmek isterseniz, bir sanal ortam oluşturup (`uv venv` & `source .venv/bin/activate`) bu bağımlılıkları `uv pip install -r requirements.txt` ile kurabilirsiniz.

🚀 **Claude Desktop Entegrasyonu (`fastmcp install` ile - Önerilen)**

1.  Terminalde `yoktez_mcp_server.py` dosyasının bulunduğu `yoktez-mcp` dizininde olduğunuzdan emin olun.
2.  Aşağıdaki komutu çalıştırın (bu komut sizin tarafınızdan doğrulanmıştı):

    ```bash
    fastmcp install yoktez_mcp_server.py \
        --name "YokTez MCP" \
        --with beautifulsoup4 \
        --with httpx \
        --with 'markitdown[pdf]' \
        --with playwright \
        --with pydantic \
        --with pypdf \
        --with ftfy \
        --with lxml
    ```
    * `--name "YokTez MCP"`: Araç Claude Desktop'ta bu isimle görünecektir.
    * `--with ...`: Sunucunun çalışması için gereken Python bağımlılıklarını belirtir. `fastmcp` kütüphanesinin kendisi, bu komutla kurulan izole ortama `fastmcp install` tarafından otomatik olarak eklenecektir.

    Bu komut, `uv` kullanarak sunucunuz için izole bir Python ortamı oluşturacak, belirtilen bağımlılıkları kuracak ve aracı Claude Desktop uygulamasına kaydedecektir.

⚙️ **Claude Desktop Manuel Kurulumu (Yapılandırma Dosyası ile - Alternatif)**

1.  Claude Desktop **Ayarları -> Developer -> Edit Config** yolunu izleyin.
2.  Açılan `claude_desktop_config.json` dosyasına `mcpServers` nesnesi altına aşağıdaki gibi bir girdi ekleyin:

    ```json
    {
      "mcpServers": {
        // ... (varsa diğer sunucu tanımlamalarınız) ...
        "YokTez MCP": {
          "command": "uv", // veya sisteminizdeki python3 yolu
          "args": [
            "run", // eğer `uv run` kullanıyorsanız
            "--with", "beautifulsoup4",
            "--with", "httpx",
            "--with", "markitdown[pdf]",
            "--with", "playwright",
            "--with", "pydantic",
            "--with", "pypdf",
            "--with", "ftfy",
            "--with", "lxml",
            "--with", "fastmcp", // fastmcp'nin kendisi de lazım
            "fastmcp", "run", 
            "/TAM/PROJE/YOLUNUZ/yoktez-mcp/yoktez_mcp_server.py" 
            // Yukarıdaki satırı python yoktez_mcp_server.py olarak da deneyebilirsiniz,
            // eğer fastmcp run gerekli değilse ve server __main__ altında app.run() ile başlıyorsa.
          ]
        }
      }
    }
    ```
    * **Önemli:** `/TAM/PROJE/YOLUNUZ/yoktez-mcp/yoktez_mcp_server.py` kısmını dosyanın sisteminizdeki **tam yolu** ile değiştirin.
3.  Claude Desktop'ı yeniden başlatın.

🛠️ **Kullanılabilir Araçlar (MCP Tools)**

Bu FastMCP sunucusu aşağıdaki temel araçları sunar:

* **`search_yok_tez_detailed`**: YÖK Ulusal Tez Merkezi'nde çeşitli kriterlere göre detaylı tez araması yapar.
    * **Parametreler:** `tez_ad`, `yazar_ad_soyad`, `danisman_ad_soyad`, `universite_ad`, `enstitu_ad`, `anabilim_dal_ad`, `bilim_dal_ad`, `tez_no`, `konu_basliklari`, `dizin_terimleri`, `ozet_metni`, `tez_turu`, `izin_durumu`, `tez_durumu`, `dil`, `enstitu_grubu`, `yil_baslangic`, `yil_bitis`, `page`, `results_per_page`.
    * **Döndürdüğü Değer:** `YokTezSearchResult` (Tez özetlerinin sayfalanmış listesi, toplam sonuç sayısı vb.)

* **`get_yok_tez_document_markdown`**: Belirli bir tezin PDF içeriğini, istenen PDF sayfasına göre Markdown formatında getirir.
    * **Parametreler:** `detail_page_url` (tez detay sayfası URL'si), `page_number` (istenen PDF sayfa numarası).
    * **Döndürdüğü Değer:** `YokTezDocumentMarkdown` (İlgili sayfanın Markdown içeriği, toplam sayfa sayısı, metadata vb.)

📜 **Lisans**

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.