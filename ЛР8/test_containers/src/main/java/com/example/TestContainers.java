package com.example;

import java.awt.BorderLayout;
import java.util.Date;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.Random;

import javax.swing.JFrame;
import javax.swing.SwingUtilities;

import org.jfree.chart.ChartFactory;
import org.jfree.chart.ChartPanel;
import org.jfree.chart.JFreeChart;
import org.jfree.chart.plot.PlotOrientation;
import org.jfree.data.xy.XYSeries;
import org.jfree.data.xy.XYSeriesCollection;

// Класс для измерения времени выполнения операций
class MyTimer {
    Date d = new Date(); // Сохраняем текущее время при создании объекта

    public void printTime(String text) {
        // Выводим текст и разницу между текущим временем и временем создания объекта
        System.out.println(text + ": " + (new Date().getTime() - d.getTime()) + " ms");
    }
}

public class TestContainers {
    private static XYSeries hashSetAddSeries = new XYSeries("HashSet - добавление");
    private static XYSeries linkedListAddSeries = new XYSeries("LinkedList - добавление");

    private static XYSeries hashSetSearchSeries = new XYSeries("HashSet - поиск");
    private static XYSeries linkedListSearchSeries = new XYSeries("LinkedList - поиск");

    public static void main(String[] args) {
        HashSet<Integer> hashSet = new HashSet<>();
        LinkedList<Integer> linkedList = new LinkedList<>();
        Random random = new Random();

        int start = 20000;
        int end = 200000;
        int step = 20000;
        int size = (end - start) / step + 1;
        
        int[] sizes = new int[size];
        for (int i = 0, sizeValue = start; sizeValue <= end; sizeValue += step, i++) {
            sizes[i] = sizeValue;
        }

        int numberOfSearches = 100000;

        System.out.println("===== Добавление элементов =====");
        for (int sample : sizes) {
            hashSet.clear();
            linkedList.clear();
            System.out.println("n = " + sample);

            // Добавление в HashSet
            MyTimer timer1 = new MyTimer();
            for (int i = 0; i < sample; i++) {
                hashSet.add(random.nextInt());
            }
            long addTimeHashSet = new Date().getTime() - timer1.d.getTime(); // Время добавления
            timer1.printTime("Добавление в HashSet");
            hashSetAddSeries.add(sample, addTimeHashSet);

            // Добавление в LinkedList
            MyTimer timer2 = new MyTimer();
            for (int i = 0; i < sample; i++) {
                linkedList.addFirst(random.nextInt());
            }
            long addTimeLinkedList = new Date().getTime() - timer2.d.getTime(); // Время добавления
            timer2.printTime("Добавление в LinkedList");
            linkedListAddSeries.add(sample, addTimeLinkedList);
        }

        System.out.println("\n===== Поиск элементов =====");
        for (int sample : sizes) {
            hashSet.clear();
            linkedList.clear();

            // Заполнение контейнеров
            for (int i = 0; i < sample; i++) {
                int value = random.nextInt();
                hashSet.add(value);
                linkedList.addFirst(value);
            }

            System.out.println("n = " + sample);

            // Поиск в HashSet
            MyTimer timer3 = new MyTimer();
            for (int i = 0; i < numberOfSearches; i++) {
                hashSet.contains(random.nextInt());
            }
            long searchTimeHashSet = new Date().getTime() - timer3.d.getTime(); // Время поиска
            timer3.printTime("Поиск в HashSet");
            hashSetSearchSeries.add(sample, searchTimeHashSet);

            // Поиск в LinkedList
            MyTimer timer4 = new MyTimer();
            for (int i = 0; i < numberOfSearches; i++) {
                linkedList.contains(random.nextInt());
            }
            long searchTimeLinkedList = new Date().getTime() - timer4.d.getTime(); // Время поиска
            timer4.printTime("Поиск в LinkedList");
            linkedListSearchSeries.add(sample, searchTimeLinkedList);
        }

        // Строим графики для добавления элементов
        createAddChart("Время добавления элементов в HashSet", "Количество элементов", "Время (мс)", hashSetAddSeries);
        createAddChart("Время добавления элементов в LinkedList", "Количество элементов", "Время (мс)", linkedListAddSeries);

        // Строим графики для поиска элементов
        createSearchChart("Время поиска элементов в HashSet", "Количество элементов", "Время (мс)", hashSetSearchSeries);
        createSearchChart("Время поиска элементов в LinkedList", "Количество элементов", "Время (мс)", linkedListSearchSeries);
    }

    // Функция для построения графика добавления элементов
    private static void createAddChart(String title, String xAxisLabel, String yAxisLabel, XYSeries series) {
        XYSeriesCollection dataset = new XYSeriesCollection();
        dataset.addSeries(series);

        JFreeChart chart = ChartFactory.createXYLineChart(
                title,
                xAxisLabel,
                yAxisLabel,
                dataset,
                PlotOrientation.VERTICAL,
                true,
                true,
                false
        );

        SwingUtilities.invokeLater(() -> {
            JFrame frame = new JFrame(title);
            frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
            frame.setLayout(new BorderLayout());
            ChartPanel chartPanel = new ChartPanel(chart);
            frame.add(chartPanel, BorderLayout.CENTER);
            frame.pack();
            frame.setLocationRelativeTo(null);
            frame.setVisible(true);
        });
    }

    // Функция для построения графика поиска элементов
    private static void createSearchChart(String title, String xAxisLabel, String yAxisLabel, XYSeries series) {
        XYSeriesCollection dataset = new XYSeriesCollection();
        dataset.addSeries(series);

        JFreeChart chart = ChartFactory.createXYLineChart(
                title,
                xAxisLabel,
                yAxisLabel,
                dataset,
                PlotOrientation.VERTICAL,
                true,
                true,
                false
        );

        SwingUtilities.invokeLater(() -> {
            JFrame frame = new JFrame(title);
            frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
            frame.setLayout(new BorderLayout());
            ChartPanel chartPanel = new ChartPanel(chart);
            frame.add(chartPanel, BorderLayout.CENTER);
            frame.pack();
            frame.setLocationRelativeTo(null);
            frame.setVisible(true);
        });
    }
}
