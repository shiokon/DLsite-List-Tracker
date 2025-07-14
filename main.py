import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, scrolledtext
import csv
import os
from PIL import Image, ImageTk
import webbrowser
import requests
from bs4 import BeautifulSoup
from io import BytesIO
import re
from datetime import datetime
from tkcalendar import DateEntry
from collections import defaultdict


class MangaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("list")
        self.root.state('zoomed')
        self.root.geometry('1200x800')
        self.desired_height = 400

        self.images_data = []
        self.page_size = 100
        self.current_page = 0
        self.filtered_data = []
        self.authors = {}
        self.filtered_authors = set()
        self.excluded_authors = set()

        self.build_ui()
        self.load_data()
        self.filter_data("All")
        

    def build_ui(self):
        controls = tk.Frame(self.root)
        controls.pack(fill="x", pady=5)

        self.add_button = tk.Button(controls, text="Add Manga", command=self.add_manga)
        self.add_button.pack(side="right", padx=10)

        self.stats_label = tk.Label(controls, font=("Helvetica", 10))
        self.stats_label.pack(side="right", padx=10)

        self.stats_button = tk.Button(controls, text="Stats", command=self.open_stats_window)
        self.stats_button.pack(side="right", padx=5)

        filter_entry_frame = tk.Frame(controls)
        filter_entry_frame.pack(side="left", padx=10)
        tk.Label(filter_entry_frame, text="Filter Authors:").pack(anchor="w")
        self.filterauthor_entry = tk.Entry(filter_entry_frame, width=30)
        self.filterauthor_entry.pack()
        self.filterauthor_entry.bind("<KeyRelease>", self.update_filter_list)

        filter_frame = tk.Frame(controls)
        filter_frame.pack(side="left", padx=10)
        self.filter_listbox = tk.Listbox(filter_frame, selectmode="multiple", height=5, width=30, exportselection=False)
        self.filter_listbox.pack(side="left")
        scrollbar = tk.Scrollbar(filter_frame, orient="vertical", command=self.filter_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.filter_listbox.config(yscrollcommand=scrollbar.set)
        self.filter_listbox.bind('<<ListboxSelect>>', lambda e: self.filter_data(self.notebook.tab(self.notebook.select(), "text")))

        exclude_entry_frame = tk.Frame(controls)
        exclude_entry_frame.pack(side="left", padx=10)
        tk.Label(exclude_entry_frame, text="Exclude Authors:").pack(anchor="w")
        self.author_entry = tk.Entry(exclude_entry_frame, width=30)
        self.author_entry.pack()
        self.author_entry.bind("<KeyRelease>", self.update_exclude_list)

        exclude_frame = tk.Frame(controls)
        exclude_frame.pack(side="left", padx=10)
        self.exclude_listbox = tk.Listbox(exclude_frame, selectmode="multiple", height=5, width=30, exportselection=False)
        self.exclude_listbox.pack(side="left")
        scrollbar = tk.Scrollbar(exclude_frame, orient="vertical", command=self.exclude_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.exclude_listbox.config(yscrollcommand=scrollbar.set)
        self.exclude_listbox.bind('<<ListboxSelect>>', lambda e: self.filter_data(self.notebook.tab(self.notebook.select(), "text")))

        self.filter_listbox.bind("<Enter>", self.disable_canvas_scroll)
        self.filter_listbox.bind("<Leave>", self.enable_canvas_scroll)

        self.exclude_listbox.bind("<Enter>", self.disable_canvas_scroll)
        self.exclude_listbox.bind("<Leave>", self.enable_canvas_scroll)




        sorter_frame = tk.Frame(controls)
        sorter_frame.pack(side="left", padx=10)
        
        sort_by_label = tk.Label(sorter_frame, text="Sort By")
        sort_by_label.pack(side="left", padx=5)

        self.selected_sort = tk.StringVar()
        self.selected_sort.set("Release Date")

        self.reverse_var = tk.BooleanVar()

        sort_options = ["Release Date", "Title", "Author", "Date Added", "Score"]

        sort_by_dropdown = tk.OptionMenu(sorter_frame, self.selected_sort, *sort_options)
        sort_by_dropdown.pack(side="left", padx=5)

        reverse_checkbox = tk.Checkbutton(sorter_frame, text="Reverse Order", variable=self.reverse_var)
        reverse_checkbox.pack(side="left", padx=5)

        apply_button = tk.Button(sorter_frame, text="Apply Sorting", command=self.apply_sorting)
        apply_button.pack(side="left", padx=5)


        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="x")
        self.tabs = {
            "All": tk.Frame(self.notebook),
            "Reading": tk.Frame(self.notebook),
            "Finished": tk.Frame(self.notebook),
            "Unavailable": tk.Frame(self.notebook),
        }

        for name, tab in self.tabs.items():
            self.notebook.add(tab, text=name)
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

        self.frame = tk.Frame(self.root)
        self.frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.canvas = tk.Canvas(self.frame)
        self.scroll_y = tk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.scroll_y.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.image_frame = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.image_frame, anchor="nw")

        self.image_frame.bind("<Configure>", self.update_scrollregion)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        controls_bottom = tk.Frame(self.root)
        controls_bottom.pack(fill="x", pady=5)
    

        self.prev_button = tk.Button(controls_bottom, text="Previous Page", command=self.prev_page)
        self.prev_button.pack(side="left", padx=10)

        self.footer = tk.Label(controls_bottom, text="", anchor="center")
        self.footer.pack(side="left", expand=True)

        self.next_button = tk.Button(controls_bottom, text="Next Page", command=self.next_page)
        self.next_button.pack(side="right", padx=10)

        self.page_entry = tk.Entry(controls_bottom, width=5)
        self.page_entry.bind("<Return>", lambda event: (self.skip_to_page(), self.page_entry.delete(0, tk.END), self.go_button.focus()))
        self.page_entry.pack(side="right", padx=(5, 0))

        self.go_button = tk.Button(controls_bottom, text="Go", command=lambda: (self.skip_to_page(), self.page_entry.delete(0, tk.END), self.go_button.focus()))
        self.go_button.pack(side="right")

    def open_stats_window(self):
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Manga Stats")
        stats_window.geometry("600x600")

        bbcode_text = self.generate_bbcode()

        text_area = scrolledtext.ScrolledText(stats_window, width=70, height=20, wrap=tk.WORD)
        text_area.insert(tk.END, bbcode_text)
        text_area.pack(padx=10, pady=10)
        text_area.config(state=tk.DISABLED)
        
        copy_label = tk.Label(stats_window, text="Copy the text above in BBCode format.")
        copy_label.pack(pady=5)


    def update_scrollregion(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def disable_canvas_scroll(self, event):
        self.canvas.unbind_all("<MouseWheel>")

    def enable_canvas_scroll(self, event):
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

    def apply_sorting(self):
        sort_criteria = self.selected_sort.get()
        reverse = self.reverse_var.get()

        self.load_data(sort_criteria, reverse)
        self.filter_data("All")

    def generate_bbcode(self):
        finished_manga = [d for d in self.images_data if d['status'] == 'Finished']

        finished_manga.sort(key=lambda x: (x['author'], datetime.strptime(x['end_date'], '%Y-%m-%d')))

        bbcode_text = ""
        current_author = None
        author_entries = defaultdict(list)

        for manga in finished_manga:
            author_entries[manga['author']].append(manga)

        for author in sorted(author_entries.keys()):
            mangas = author_entries[author]

            scores = [int(m['score']) for m in mangas if m['score'].isdigit()]
            avg_score = round(sum(scores) / len(scores), 2) if scores else '-'

            bbcode_text += f'[b][u]{author}[/u][/b] [Average Score: {avg_score}]\n'

            for manga in mangas:
                title = manga['title']
                start_date = datetime.strptime(manga['start_date'], '%Y-%m-%d').strftime('%m/%d/%y')
                end_date = datetime.strptime(manga['end_date'], '%Y-%m-%d').strftime('%m/%d/%y')
                score = manga['score'] if manga['score'].isdigit() else 'N/A'
                bbcode_text += f'{start_date} - {end_date}: {title} [Score: {score}]\n'

            bbcode_text += "\n"

        bbcode_text = f'[spoiler="stats"]\n{bbcode_text}[/spoiler]'

        return bbcode_text



    def load_data(self, sort_criteria=None, reverse=False):
        if not os.path.exists('manga_data.csv'):
            return
        
        self.images_data.clear()
        self.authors.clear()

        with open('manga_data.csv', 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None)
            for line in reader:
                if len(line) < 6: continue
                url, img_path, author, title, release_date, status, start_date, end_date, score = line
                try:
                    if " " in release_date:
                        release_date = release_date.split(" ")[0]
                    img = Image.open(img_path)
                    height = self.desired_height
                    width = int((img.width / img.height) * height)
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                    img_tk = ImageTk.PhotoImage(img)
                    self.images_data.append({
                        'url': url,
                        'img_path': img_path,
                        'image': img_tk,
                        'author': author,
                        'title': title,
                        'release_date': release_date,
                        'status': status,
                        'start_date': start_date,
                        'end_date': end_date,
                        'score': score
                    })
                    self.authors[author] = self.authors.get(author, 0) + 1
                except Exception as e:
                    print(f"Error loading image: {img_path} - {e}")

        if sort_criteria:
            if sort_criteria == "Release Date":
                self.images_data.sort(key=lambda x: x['release_date'], reverse=reverse)
            elif sort_criteria == "Title":
                self.images_data.sort(key=lambda x: x['title'], reverse=reverse)
            elif sort_criteria == "Author":
                self.images_data.sort(key=lambda x: x['author'], reverse=reverse)
            elif sort_criteria == "Date Added":
                indexed_data = list(enumerate(self.images_data))
                indexed_data.sort(key=lambda x: x[0], reverse=reverse)
                self.images_data = [item for idx, item in indexed_data]
            elif sort_criteria == "Score":
                self.images_data.sort(key=lambda x: x['score'], reverse=reverse)
        else:
            self.images_data.sort(key=lambda x: x['release_date'])


        sorted_authors = sorted(self.authors.items(), key=lambda x: x[1], reverse=True)
        self.filter_listbox.delete(0, tk.END)
        for author, count in sorted_authors:
            self.filter_listbox.insert(tk.END, f"{author} ({count})")

        self.exclude_listbox.delete(0, tk.END)
        for author, count in sorted_authors:
            self.exclude_listbox.insert(tk.END, f"{author} ({count})")

    def add_manga(self):
        url = simpledialog.askstring("Add Manga", "Paste DLsite URL:")
        if not url:
            return
        
        if '.html' in url:
            url = url.split('.html')[0] + '.html'

        if self.manga_exists(url):
            messagebox.showwarning("Warning", "This manga is already in the list.")
            return

        try:
            title, author, release_date = self.get_dlsite_details(url)
            image_url = self.get_dlsite_image(url)
            image_path = self.save_image(image_url)
            with open('manga_data.csv', 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([url, image_path, author, title, release_date, "", "", "", "-"])
            #messagebox.showinfo("Success", f"Added: {title}")
            self.images_data.clear()
            self.authors.clear()
            self.load_data()
            self.filter_data("All")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def manga_exists(self, url):
        if not os.path.exists('manga_data.csv'):
            return False
        with open('manga_data.csv', 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader, None)
            for line in reader:
                if len(line) < 6:
                    continue
                existing_url = line[0]
                if existing_url == url:
                    return True
        return False

    def get_dlsite_details(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True).split(' | ')[0] if title_tag else "Unknown"
        title = re.sub(r'【\d+%OFF】', '', title).strip()
        title = re.sub(r'\s*\[.*?\]$', '', title).strip()

        author = "Unknown"
        circle_tag = soup.find('th', string="サークル名")
        if circle_tag:
            author = circle_tag.find_next('td').get_text(strip=True)
        else:
            author_tag = soup.find('th', string="著者")
            if author_tag:
                author = author_tag.find_next('td').get_text(strip=True)

        title = re.sub(rf'\s*\[{re.escape(author)}\]$', '', title).strip()

        release_tag = soup.find('th', string="販売日")
        raw_date = release_tag.find_next('td').get_text(strip=True) if release_tag else None
        if raw_date:
            match = re.match(r"(\d{4})年(\d{2})月(\d{2})日", raw_date)
            if match:
                release_date = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            else:
                release_date = datetime.today().strftime('%Y-%m-%d')
        else:
            release_date = datetime.today().strftime('%Y-%m-%d')

        return title, author, release_date

    def get_dlsite_image(self, url):
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        img_tag = soup.find('meta', property='og:image')
        return img_tag['content'] if img_tag else None

    def save_image(self, image_url):
        os.makedirs("images", exist_ok=True)
        image_name = image_url.split("/")[-1].split("?")[0]
        image_path = os.path.join("images", image_name)
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        img.save(image_path)
        return image_path

    def get_selected_filtered_authors(self):
        selected_indices = self.filter_listbox.curselection()
        selected_names = []
        for i in selected_indices:
            item = self.filter_listbox.get(i)
            author = item.split(" (")[0]
            selected_names.append(author)
        return set(selected_names)
    
    def update_filter_list(self, event=None):
        search_query = self.filterauthor_entry.get().lower()

        filtered_authors = [(author, count) for author, count in self.authors.items() if search_query in author.lower()]
        filtered_authors.sort(key=lambda x: x[1], reverse=True)

        self.filter_listbox.delete(0, tk.END)

        for author, count in filtered_authors:
            self.filter_listbox.insert(tk.END, f"{author} ({count})")

    def get_selected_excluded_authors(self):
        selected_indices = self.exclude_listbox.curselection()
        selected_names = []
        for i in selected_indices:
            item = self.exclude_listbox.get(i)
            author = item.split(" (")[0]
            selected_names.append(author)
        return set(selected_names)

    def update_exclude_list(self, event=None):
        search_query = self.author_entry.get().lower()

        filtered_authors = [(author, count) for author, count in self.authors.items() if search_query in author.lower()]
        filtered_authors.sort(key=lambda x: x[1], reverse=True)

        self.exclude_listbox.delete(0, tk.END)

        for author, count in filtered_authors:
            self.exclude_listbox.insert(tk.END, f"{author} ({count})")


    def filter_data(self, tab_name):
        self.filtered_authors = self.get_selected_filtered_authors()
        self.excluded_authors = self.get_selected_excluded_authors()

        if tab_name == "All":
            temp_data = [d for d in self.images_data if d['status'] != "Unavailable"]
        else:
            temp_data = [d for d in self.images_data if d['status'] == tab_name]

        if self.filtered_authors:
            temp_data = [d for d in temp_data if d['author'] in self.filtered_authors]

        if self.excluded_authors:
            temp_data = [d for d in temp_data if d['author'] not in self.excluded_authors]

        self.filtered_data = temp_data
        self.current_page = 0
        self.display_page()

        self.reading_count = len([d for d in self.images_data if d['status'] == "Reading"])
        self.finished_count = len([d for d in self.images_data if d['status'] == "Finished"])
        self.update_stats_tab()

    def update_stats_tab(self):
        stats_text = f"Reading: {self.reading_count}\tFinished: {self.finished_count}\t"
        self.stats_label.config(text=stats_text)


    def on_tab_change(self, event):
        tab = event.widget.tab(event.widget.index("current"))["text"]
        self.filter_data(tab)

    def skip_to_page(self):
        try:
            page = int(self.page_entry.get()) - 1
            max_page = max((len(self.filtered_data) - 1) // self.page_size, 0)
            if 0 <= page <= max_page:
                self.current_page = page
                self.canvas.yview_moveto(0)
                self.display_page()
            else:
                messagebox.showwarning("Invalid Page", f"Please enter a number between 1 and {max_page + 1}.")
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid page number.")
        


    def display_page(self):
        for widget in self.image_frame.winfo_children():
            widget.destroy()

        start = self.current_page * self.page_size
        end = start + self.page_size
        page_images = self.filtered_data[start:end]

        self.row = 0
        self.col = 0

        for data in page_images:
            entry_frame = tk.Frame(self.image_frame, bd=1, relief="solid")
            bg_color = "#90EE90" if data['status'] == "Reading" else "#ADD8E6" if data['status'] == "Finished" \
            else "#EE5353" if data['status'] == "Unavailable" else None
            entry_frame.config(bg=bg_color)
            entry_frame.grid(row=self.row, column=self.col, padx=10, pady=10)

            tk.Label(entry_frame, text=data['author'], font=("Arial", 10, "bold"), anchor="center", wraplength=400, justify="center", bg=bg_color).pack()
            tk.Label(entry_frame, text=data['title'], font=("Arial", 15), anchor="center", wraplength=400, justify="center", bg=bg_color).pack()
            tk.Button(entry_frame, image=data['image'], command=lambda d=data: self.show_popup(d)).pack()

            self.col += 1
            if self.col >= 4:
                self.col = 0
                self.row += 1

        total_pages = max(1, (len(self.filtered_data) + self.page_size - 1) // self.page_size)
        self.footer.config(text=f"Page {self.current_page + 1} of {total_pages}")
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.canvas.yview_moveto(0)
            self.display_page()

    def next_page(self):
        if (self.current_page + 1) * self.page_size < len(self.filtered_data):
            self.current_page += 1
            self.canvas.yview_moveto(0)
            self.display_page()

    def show_popup(self, data):
        popup = tk.Toplevel(self.root)
        popup.title("Manga Details")

        main_window_x = self.root.winfo_x() 
        main_window_y = self.root.winfo_y() 

        popup.geometry(f"500x850+{main_window_x + 100}+{main_window_y + 100}")

        tk.Label(popup, text=f"Author: {data['author']}", font=("Arial", 12)).pack(pady=5)
        tk.Label(popup, text=f"Title: {data['title']}", font=("Arial", 14, "bold"), wraplength=480).pack(pady=5)

        img = Image.open(data['img_path'])
        img = img.resize((int((img.width / img.height) * 300), 300), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        img_label = tk.Label(popup, image=img_tk)
        img_label.image = img_tk
        img_label.pack(pady=10)

        tk.Label(popup, text=f"Release Date: {data['release_date']}", font=("Arial", 12)).pack(pady=5)
        tk.Button(popup, text="Open in DLsite", command=lambda: (webbrowser.open(data['url']), popup.destroy())).pack(pady=10)
        
        tk.Label(popup, text="Start Date:").pack()
        start_date_entry = DateEntry(popup, width=20, date_pattern='yyyy-mm-dd')
        start_date_entry.pack(pady=2)
        if data.get('start_date'):
            start_date_entry.set_date(data['start_date'])
        else:
            start_date_entry.delete(0, tk.END)

        tk.Label(popup, text="Finished Date:").pack()
        end_date_entry = DateEntry(popup, width=20, date_pattern='yyyy-mm-dd')
        end_date_entry.pack(pady=2)
        if data.get('end_date'):
            end_date_entry.set_date(data['end_date'])
        else:
            end_date_entry.delete(0, tk.END)

        tk.Label(popup, text="Score:").pack()
        score_var = tk.StringVar(value=data.get('score', '-'))
        score_dropdown = ttk.Combobox(popup, textvariable=score_var, values=['-'] + [str(i) for i in range(1, 11)], state="readonly")
        score_dropdown.pack(pady=5)



        def update_status(new_status):
            if new_status == "":
                data['status'] = ""
                data['start_date'] = ""
                data['end_date'] = ""
                data['score'] = "-"
            else:
                data['status'] = new_status
                data['start_date'] = start_date_entry.get()
                data['end_date'] = end_date_entry.get()
                data['score'] = score_var.get()


            with open('manga_data.csv', 'w', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['url', 'img_path', 'author', 'title', 'release_date', 'status', 'start_date', 'end_date', 'score'])
                for row in self.images_data:
                    if row['url'] == data['url']:
                        row.update(data)
                    writer.writerow([
                        row.get('url', ''),
                        row.get('img_path', ''),
                        row.get('author', ''),
                        row.get('title', ''),
                        row.get('release_date', ''),
                        row.get('status', ''),
                        row.get('start_date', ''),
                        row.get('end_date', ''),
                        row.get('score', '-')
                    ])

            popup.destroy()
            self.display_page()

        if data['status'] == "Reading":
            tk.Button(popup, text="Remove from Reading", command=lambda: update_status("")).pack(pady=5)
        else:
            tk.Button(popup, text="Add to Reading", command=lambda: update_status("Reading")).pack(pady=5)

        if data['status'] == "Finished":
            tk.Button(popup, text="Remove from Finished", command=lambda: update_status("")).pack(pady=5)
        else:
            tk.Button(popup, text="Add to Finished", command=lambda: update_status("Finished")).pack(pady=5)

        if data['status'] in ["Reading", "Finished"]:
            tk.Button(popup, text="Update Info", command=lambda: update_status(data['status'])).pack(pady=5)


        def delete_manga():
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{data['title']}'?")
            if confirm:
                try:
                    if os.path.exists(data['img_path']):
                        os.remove(data['img_path'])

                    with open('manga_data.csv', 'r', encoding='utf-8') as file:
                        reader = csv.DictReader(file)
                        all_data = list(reader)

                    self.images_data = [d for d in all_data if d['url'] != data['url']]

                    with open('manga_data.csv', 'w', encoding='utf-8', newline='') as file:
                        writer = csv.DictWriter(file, fieldnames=['url', 'img_path', 'author', 'title', 'release_date', 'status', 'start_date', 'end_date', 'score'])
                        writer.writeheader()
                        writer.writerows(self.images_data)

                    popup.destroy()
                    self.display_page()
                    messagebox.showinfo("Deleted", f"'{data['title']}' was deleted successfully.")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete manga: {e}")

        tk.Button(popup, text="Delete Manga", fg="red", command=delete_manga).pack(pady=10)

        if data['status'] == "Unavailable":
            tk.Button(popup, text="Unmark as Unavailable", command=lambda: update_status("")).pack(pady=5)
        else:
            tk.Button(popup, text="Mark as Unavailable", command=lambda: update_status("Unavailable")).pack(pady=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = MangaApp(root)
    root.mainloop()
